import { useMutation } from "@apollo/client/react";
import { type FormEvent, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { errorMessage } from "../errors";
import { LOGIN, ME, REGISTER } from "../graphql/operations";

const MIN_PASSWORD = 10; // PASSWORD_MIN_LENGTH del auth-service
const input = "w-full rounded-md border border-slate-300 px-3 py-2 focus:border-sky-600 focus:outline-none";

/** Login y registro (tarea 4.7). Tras autenticarse vuelve a `?next=` (p. ej. el checkout). */
export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const requested = params.get("next");
  const next = requested && requested.startsWith("/") && !requested.startsWith("//") ? requested : "/search";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const options = { refetchQueries: [ME], awaitRefetchQueries: true };
  const [login, loginState] = useMutation(LOGIN, options);
  const [register, registerState] = useMutation(REGISTER, options);
  const state = mode === "login" ? loginState : registerState;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLocalError(null);
    if (mode === "register") {
      if (password.length < MIN_PASSWORD) {
        setLocalError(`La contraseña debe tener al menos ${MIN_PASSWORD} caracteres.`);
        return;
      }
      if (password !== confirm) {
        setLocalError("Las contraseñas no coinciden.");
        return;
      }
      const result = await register({ variables: { input: { fullName, email, password } } }).catch(() => null);
      if (result?.data?.register) navigate(next);
    } else {
      const result = await login({ variables: { input: { email, password } } }).catch(() => null);
      if (result?.data?.login) navigate(next);
    }
  }

  function switchMode(target: "login" | "register") {
    setMode(target);
    setLocalError(null);
  }

  const error = localError ?? errorMessage(state.error);
  return (
    <section className="mx-auto max-w-sm rounded-xl bg-white p-6 shadow">
      <div className="mb-5 grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-sm">
        <button type="button" onClick={() => switchMode("login")}
                className={`rounded-md py-1.5 ${mode === "login" ? "bg-white font-medium shadow" : "text-slate-500"}`}>
          Iniciar sesión
        </button>
        <button type="button" onClick={() => switchMode("register")}
                className={`rounded-md py-1.5 ${mode === "register" ? "bg-white font-medium shadow" : "text-slate-500"}`}>
          Crear cuenta
        </button>
      </div>
      <form onSubmit={handleSubmit} className="space-y-3">
        {mode === "register" && (
          <input required placeholder="Nombre completo" value={fullName} onChange={(e) => setFullName(e.target.value)}
                 className={input} autoComplete="name" />
        )}
        <input type="email" required placeholder="Correo" value={email} onChange={(e) => setEmail(e.target.value)}
               className={input} autoComplete="email" />
        <input type="password" required placeholder="Contraseña" value={password} onChange={(e) => setPassword(e.target.value)}
               className={input} autoComplete={mode === "login" ? "current-password" : "new-password"}
               minLength={mode === "register" ? MIN_PASSWORD : undefined} />
        {mode === "register" && (
          <input type="password" required placeholder="Repite la contraseña" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                 className={input} autoComplete="new-password" />
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={state.loading} className="w-full rounded-md bg-sky-700 py-2 font-medium text-white hover:bg-sky-800 disabled:opacity-50">
          {state.loading ? "Un momento…" : mode === "login" ? "Entrar" : "Crear cuenta"}
        </button>
      </form>
      {mode === "register" && (
        <p className="mt-3 text-xs text-slate-500">Mínimo {MIN_PASSWORD} caracteres. La contraseña se guarda con Argon2id.</p>
      )}
    </section>
  );
}
