from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from graphql import GraphQLError
from graphql.language import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    OperationDefinitionNode,
    SelectionSetNode,
)
from graphql.validation import NoSchemaIntrospectionCustomRule, ValidationRule
from strawberry.fastapi import GraphQLRouter
from starlette.types import RequestResponseEndpoint

from config import settings
from limiter import redis_client
from schema import get_context, schema
from wandersync_common.errors import register_exception_handlers
from wandersync_common.health import health_router
from wandersync_common.logging import configure_logging
from wandersync_common.middleware import CorrelationIdMiddleware


class MaximumDepthRule(ValidationRule):
    def enter_operation_definition(self, node: OperationDefinitionNode, *_: Any) -> None:
        fragments = {
            definition.name.value: definition
            for definition in self.context.document.definitions
            if isinstance(definition, FragmentDefinitionNode)
        }
        if _selection_depth(node.selection_set, fragments) > settings.graphql_max_depth:
            self.report_error(
                GraphQLError(
                    f"Query depth exceeds the limit of {settings.graphql_max_depth}",
                    nodes=node,
                    extensions={"code": "BAD_USER_INPUT"},
                )
            )


def _selection_depth(
    selection_set: SelectionSetNode,
    fragments: dict[str, FragmentDefinitionNode],
    depth: int = 0,
    fragment_stack: frozenset[str] = frozenset(),
) -> int:
    if not selection_set.selections:
        return depth
    nested_depths = []
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode) and selection.selection_set is not None:
            nested_depths.append(_selection_depth(selection.selection_set, fragments, depth + 1, fragment_stack))
        elif isinstance(selection, InlineFragmentNode):
            nested_depths.append(
                _selection_depth(selection.selection_set, fragments, depth, fragment_stack)
            )
        elif isinstance(selection, FragmentSpreadNode):
            name = selection.name.value
            fragment = fragments.get(name)
            if fragment is not None and name not in fragment_stack:
                nested_depths.append(
                    _selection_depth(
                        fragment.selection_set,
                        fragments,
                        depth,
                        fragment_stack | {name},
                    )
                )
    return max(nested_depths, default=depth + 1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.http_client = httpx.AsyncClient(timeout=15.0)
    try:
        await redis_client.ping()
        yield
    finally:
        await app.state.http_client.aclose()
        await redis_client.aclose()


async def check_redis() -> None:
    await redis_client.ping()


configure_logging(settings.service_name, settings.log_level)
app = FastAPI(title=settings.service_name, lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Content-Type",
        "X-WanderSync-CSRF",
        "X-Correlation-ID",
    ],
)
register_exception_handlers(app)
app.include_router(health_router({"redis": check_redis}))


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


validation_rules: list[type[ValidationRule]] = [MaximumDepthRule]
if not settings.graphql_introspection or settings.environment == "production":
    validation_rules.append(NoSchemaIntrospectionCustomRule)

graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
    validation_rules=validation_rules,
)
app.include_router(graphql_router, prefix="/graphql")
