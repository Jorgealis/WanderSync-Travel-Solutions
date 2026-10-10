import { useQuery } from "@apollo/client/react";
import { type ReactNode, useEffect } from "react";
import { Link, useParams } from "react-router";

import { CarSummary, FlightSummary, HotelSummary } from "../components/OfferCards";
import { errorMessage } from "../errors";
import { dateTime, money } from "../format";
import { ORDER_DETAIL } from "../graphql/operations";

const STEP_LABELS: Record<string, string> = {
  RESERVE_FLIGHT: "Reserva del vuelo",
  RESERVE_HOTEL: "Reserva del hotel",
  RESERVE_CAR: "Reserva del auto",
  PROCESS_PAYMENT: "Pago",
  CONFIRM_FLIGHT: "Confirmación del vuelo",
  CONFIRM_HOTEL: "Confirmación del hotel",
  CONFIRM_CAR: "Confirmación del auto",
  ISSUE_INVOICE: "Emisión de la factura",
};
const ORDER_STATUS: Record<string, { label: string; style: string }> = {
  PENDING: { label: "En proceso", style: "bg-sky-100 text-sky-800" },
  CONFIRMED: { label: "Confirmada", style: "bg-emerald-100 text-emerald-800" },
  CANCELLED: { label: "Cancelada (compensada)", style: "bg-amber-100 text-amber-800" },
  FAILED: { label: "Fallida", style: "bg-red-100 text-red-800" },
};
const TERMINAL = new Set(["CONFIRMED", "CANCELLED", "FAILED"]);

/** Detalle de la orden con la línea de tiempo de la SAGA (tarea 4.10), consultada por polling. */
export function OrderPage() {
  const { id = "" } = useParams();
  const { data, loading, error, stopPolling } = useQuery(ORDER_DETAIL, { variables: { id }, pollInterval: 1000 });
  const order = data?.order;

  useEffect(() => {
    if (order && TERMINAL.has(order.status)) stopPolling();
  }, [order, stopPolling]);

  if (loading && !order) return <p className="text-slate-500">Cargando orden…</p>;
  if (error) return <p className="text-red-600">{errorMessage(error)}</p>;
  if (!order) return <p className="text-slate-500">Orden no encontrada.</p>;

  const status = ORDER_STATUS[order.status] ?? { label: order.status, style: "bg-slate-100" };
  const steps = [...order.saga.steps].sort((a, b) => a.startedAt.localeCompare(b.startedAt));

  return (
    <section className="grid gap-6 lg:grid-cols-5">
      <div className="space-y-4 lg:col-span-2">
        <div className="rounded-xl bg-white p-5 shadow">
          <p className="text-xs text-slate-500">Orden {order.id}</p>
          <span className={`mt-2 inline-block rounded-full px-3 py-1 text-sm font-medium ${status.style}`}>{status.label}</span>
          {order.saga.simulatedFailureAt && (
            <p className="mt-2 text-xs text-amber-700">Demo: fallo simulado en {order.saga.simulatedFailureAt}</p>
          )}
          <dl className="mt-4 space-y-1 text-sm">
            <Row label="Subtotal" value={money(order.subtotal)} />
            <Row label="Impuestos" value={money(order.taxes)} />
            <Row label="Total" value={<strong>{money(order.totalAmount)}</strong>} />
            <Row label="Pago" value={order.payment ? `${order.payment.status} · ${order.payment.providerRef ?? ""}` : "—"} />
            <Row label="Factura" value={order.invoice ? `${order.invoice.number} · ${money(order.invoice.total)}` : "—"} />
            <Row label="Creada" value={dateTime(order.createdAt)} />
          </dl>
        </div>
        {order.flight && <div className="rounded-xl bg-white p-4 shadow"><FlightSummary flight={order.flight} /></div>}
        {order.hotel && <div className="rounded-xl bg-white p-4 shadow"><HotelSummary hotel={order.hotel} /></div>}
        {order.car && <div className="rounded-xl bg-white p-4 shadow"><CarSummary car={order.car} /></div>}
      </div>

      <div className="rounded-xl bg-white p-5 shadow lg:col-span-3">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-medium">Línea de tiempo de la SAGA</h2>
          <span className="text-xs text-slate-500">SAGA {order.saga.status}{TERMINAL.has(order.status) ? "" : " · actualizando…"}</span>
        </div>
        {order.saga.failureReason && <p className="mb-3 rounded-md bg-amber-50 p-2 text-sm text-amber-800">{order.saga.failureReason}</p>}
        <ol className="relative space-y-3 border-l-2 border-slate-200 pl-5">
          {steps.map((step, index) => {
            const compensation = step.action === "COMPENSATE";
            const icon = step.status === "RUNNING" ? "⏳" : step.status === "SUCCEEDED" ? (compensation ? "↩" : "✓") : "✗";
            const color = step.status === "FAILED" ? "text-red-600" : compensation ? "text-amber-600" : step.status === "RUNNING" ? "text-sky-600" : "text-emerald-600";
            return (
              <li key={`${step.step}-${step.action}-${step.attempt}-${index}`}>
                <span className={`absolute -left-[11px] flex h-5 w-5 items-center justify-center rounded-full bg-white text-sm ${color}`}>{icon}</span>
                <p className={`text-sm font-medium ${color}`}>
                  {compensation ? "Compensación: " : ""}{STEP_LABELS[step.step] ?? step.step}
                  {step.attempt > 1 && <span className="ml-1 text-xs font-normal text-slate-500">(intento {step.attempt})</span>}
                </p>
                <p className="text-xs text-slate-500">
                  {step.status === "RUNNING" ? "en curso…" : step.status === "SUCCEEDED" ? "completado" : `falló${step.errorCode ? `: ${step.errorCode}` : ""}`}
                  {" · "}{new Date(step.startedAt).toLocaleTimeString("es-CO")}
                </p>
              </li>
            );
          })}
        </ol>
        {TERMINAL.has(order.status) && <Link to="/orders" className="mt-5 inline-block text-sm text-sky-700 underline">Ver mis órdenes</Link>}
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}
