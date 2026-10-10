import { useMutation, useQuery } from "@apollo/client/react";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { LOGOUT, ME } from "./graphql/operations";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm font-medium ${isActive ? "bg-white/15 text-white" : "text-sky-100 hover:bg-white/10"}`;

export function Layout() {
  const navigate = useNavigate();
  const { data, client } = useQuery(ME);
  const [logout] = useMutation(LOGOUT);
  const user = data?.me;

  async function handleLogout() {
    await logout();
    await client.resetStore();
    navigate("/login");
  }

  return (
    <div className="min-h-screen">
      <header className="bg-sky-700">
        <nav className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
          <Link to="/" className="mr-4 text-lg font-semibold text-white">
            WanderSync
          </Link>
          <NavLink to="/search" className={navClass}>Buscar</NavLink>
          <NavLink to="/package" className={navClass}>Paquete</NavLink>
          <NavLink to="/checkout" className={navClass}>Checkout</NavLink>
          <div className="ml-auto text-sm text-sky-100">
            {user ? (
              <span className="flex items-center gap-3">
                {user.fullName}
                <button onClick={handleLogout} className="rounded-md bg-white/15 px-3 py-1 text-white hover:bg-white/25">
                  Salir
                </button>
              </span>
            ) : (
              <NavLink to="/login" className={navClass}>Iniciar sesión</NavLink>
            )}
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
