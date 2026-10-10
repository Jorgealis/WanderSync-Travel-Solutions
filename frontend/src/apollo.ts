import { ApolloClient, HttpLink, InMemoryCache } from "@apollo/client";

// Única vía de comunicación con el backend: el API Gateway GraphQL (requisito 4.2).
// - `/graphql` es del mismo origen: Nginx (o Vite en desarrollo) lo reenvía al gateway.
// - credentials "include": la sesión viaja en la cookie HttpOnly `ws_session`.
// - X-WanderSync-CSRF: el gateway rechaza las mutaciones sin esta cabecera (protección CSRF).
export const client = new ApolloClient({
  link: new HttpLink({
    uri: import.meta.env.VITE_GRAPHQL_URL ?? "/graphql",
    credentials: "include",
    headers: { "X-WanderSync-CSRF": "1" },
  }),
  cache: new InMemoryCache(),
});
