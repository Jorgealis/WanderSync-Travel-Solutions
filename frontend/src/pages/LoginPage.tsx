import { useMutation } from "@apollo/client/react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";

import { errorMessage } from "../errors";
import { LOGIN, ME } from "../graphql/operations";

// Esqueleto funcional (3.10). La tarea 4.7 agrega el registro y la validación de formularios.
export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [login, { loading, error }] = useMutation(LOGIN, { refetchQueries: [ME], awaitRefetchQueries: true });

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const result = await login({ variables: { input: { email, password } } }).catch(() => null);
    if (result?.data?.login) navigate("/search");
  }

  return (
    <section className="mx-auto max-w-sm rounded-xl bg-white p-6 shadow">
      <h1 className="mb-4 text-xl font-semibold">Iniciar sesión</h1>
      <form onSubmit={handleSubmit} className="space-y-3">
        <input type="email" required placeholder="Correo" value={email} onChange={(e) => setEmail(e.target.value)}
               className="w-full rounded-md border border-slate-300 px-3 py-2" autoComplete="email" />
        <input type="password" required placeholder="Contraseña" value={password} onChange={(e) => setPassword(e.target.value)}
               className="w-full rounded-md border border-slate-300 px-3 py-2" autoComplete="current-password" />
        {error && <p className="text-sm text-red-600">{errorMessage(error)}</p>}
        <button disabled={loading} className="w-full rounded-md bg-sky-700 py-2 font-medium text-white hover:bg-sky-800 disabled:opacity-50">
          {loading ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </section>
  );
}
