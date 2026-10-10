import { useQuery } from "@apollo/client/react";
import { Link } from "react-router";

import { errorMessage } from "../errors";
import { dateTime, money } from "../format";
import { MY_ORDERS } from "../graphql/operations";

const LABELS: Record<string, string> = { PENDING: "En proceso", CONFIRMED: "Confirmada", CANCELLED: "Cancelada", FAILED: "Fallida" };

/** Órdenes del usuario autenticado (`myOrders`, solo las propias: autorización del gateway). */
export function OrdersPage() {
  const { data, loading, error } = useQuery(MY_ORDERS, { fetchPolicy: "cache-and-network" });
  if (loading && !data) return <p className="text-slate-500">Cargando…</p>;
  if (error) {
    return (
      <p className="text-red-600">
        {errorMessage(error)} <Link to="/login?next=/orders" className="underline">Iniciar sesión</Link>
      </p>
    );
  }
  const orders = data?.myOrders ?? [];
  return (
    <section className="rounded-xl bg-white p-6 shadow">
      <h1 className="mb-4 text-xl font-semibold">Mis órdenes</h1>
      {orders.length === 0 ? (
        <p className="text-slate-500">Aún no tienes órdenes. <Link to="/search" className="text-sky-700 underline">Arma un paquete</Link></p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="text-slate-500"><tr><th className="py-1">Fecha</th><th>Estado</th><th>Total</th><th>Demo</th><th /></tr></thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} className="border-t border-slate-100">
                <td className="py-2">{dateTime(o.createdAt)}</td>
                <td>{LABELS[o.status] ?? o.status}</td>
                <td>{money(o.totalAmount)}</td>
                <td className="text-xs text-amber-700">{o.saga.simulatedFailureAt ? `fallo en ${o.saga.simulatedFailureAt}` : ""}</td>
                <td><Link to={`/orders/${o.id}`} className="text-sky-700 underline">Ver</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
