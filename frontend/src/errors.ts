import { CombinedGraphQLErrors } from "@apollo/client";

// Mensajes para los códigos de error del contrato (docs/contratos/schema.graphql).
const MESSAGES: Record<string, string> = {
  UNAUTHENTICATED: "Correo o contraseña incorrectos, o la sesión expiró.",
  FORBIDDEN: "No tienes permiso para esta acción.",
  RATE_LIMITED: "Demasiados intentos. Espera un momento y vuelve a intentarlo.",
  BAD_USER_INPUT: "Revisa los datos ingresados.",
};

export function errorMessage(error: unknown): string | null {
  if (!error) return null;
  if (CombinedGraphQLErrors.is(error)) {
    const code = error.errors[0]?.extensions?.code;
    return (typeof code === "string" && MESSAGES[code]) || error.errors[0]?.message || "Error inesperado.";
  }
  return "No se pudo contactar al servidor.";
}
