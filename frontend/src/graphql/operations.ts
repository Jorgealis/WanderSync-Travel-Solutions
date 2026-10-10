// Operaciones GraphQL tipadas: `npm run codegen` genera sus tipos en src/gql a partir del
// contrato (docs/contratos/schema.graphql). Cada vista pide SOLO los campos que muestra.
import { graphql } from "../gql";

export const ME = graphql(`
  query Me {
    me {
      id
      email
      fullName
    }
  }
`);

export const LOGIN = graphql(`
  mutation Login($input: LoginInput!) {
    login(input: $input) {
      user {
        id
        email
        fullName
      }
    }
  }
`);

export const LOGOUT = graphql(`
  mutation Logout {
    logout
  }
`);

export const CATALOG_STATUS = graphql(`
  query CatalogStatus {
    catalogStatus {
      catalog
      totalOffers
      lastSyncAt
    }
  }
`);
