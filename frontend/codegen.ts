import type { CodegenConfig } from "@graphql-codegen/cli";

// Los tipos se generan desde el CONTRATO (docs/contratos/schema.graphql), no desde el
// gateway en marcha: el build no depende de que el backend esté levantado.
const config: CodegenConfig = {
  schema: "../docs/contratos/schema.graphql",
  documents: ["src/**/*.{ts,tsx}"],
  ignoreNoDocuments: true,
  generates: {
    "src/gql/": {
      preset: "client",
      // Sin enmascaramiento: los fragments definen QUÉ campos pide cada componente (sin over-fetching).
      presetConfig: { fragmentMasking: false },
      config: {
        useTypeImports: true,
        enumsAsTypes: true,
        scalars: { Date: "string", DateTime: "string", Decimal: "string" },
      },
    },
  },
};

export default config;
