import { useMutation, useQuery } from "@apollo/client/react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { CarSummary, FlightSummary, HotelSummary } from "../components/OfferCards";
import { errorMessage } from "../errors";
import { money } from "../format";
import type { FailurePoint } from "../gql/graphql";
import { BOOK_PACKAGE, ME } from "../graphql/operations";
import { clearSelection, estimate, loadSelection } from "../selection";

const FAILURE_OPTIONS: { value: FailurePoint | null; label: string; help: string }[] = [
  { value: null, label: "Ninguno", help: "Reserva normal: vuelo, hotel, auto, pago, confirmaciones y factura." },
  { value: "FLIGHT", label: "Vuelo", help: "Falla la reserva del vuelo: se compensa lo que haya." },
  { value: "HOTEL", label: "Hotel", help: "Se reservó el vuelo; falla el hotel → se cancela el vuelo." },
  { value: "CAR", label: "Auto", help: "Caso del enunciado: falla el auto → se cancelan hotel y vuelo." },
  { value: "PAYMENT", label: "Pago", help: "Las tres reservas OK; falla el pago → se cancelan las tres." },
];

function newIdempotencyKey(): string {
  return typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Checkout (tarea 4.9) con el panel de demo "Simular fallo en…" para mostrar la SAGA. */
export function CheckoutPage() {
  const navigate = useNavigate();
  const { data: me, loading: meLoading } = useQuery(ME);
  const [selection] = useState(loadSelection);
  const [failure, setFailure] = useState<FailurePoint | null>(null);
  // Una clave por intento de checkout: un doble clic en "Pagar" devuelve la misma orden.
  const [idempotencyKey] = useState(newIdempotencyKey);
  const [book, { loading, error }] = useMutation(BOOK_PACKAGE);

  if (!selection) {
    return (
      <section className="rounded-xl bg-white p-6 shadow">
        <h1 className="text-xl font-semibold">Checkout</h1>
        <p className="mt-2 text-slate-500">No hay un paquete seleccionado.</p>
        <Link to="/search" className="mt-3 inline-block text-sky-700 underline">Buscar un paquete</Link>
      </section>
    );
  }
  if (!meLoading && !me?.me) {
    return (
      <section className="rounded-xl bg-white p-6 shadow">
        <h1 className="text-xl font-semibold">Checkout</h1>
        <p className="mt-2 text-slate-500">Inicia sesión para reservar tu paquete. Tu selección se conserva.</p>
        <Link to="/login?next=/checkout" className="mt-3 inline-block rounded-md bg-sky-700 px-4 py-2 text-white">Iniciar sesión</Link>
      </section>
    );
  }

  async function handlePay() {
    if (!selection) return;
    const result = await book({
      variables: {
        input: {
          flightOfferId: selection.flight.id,
          hotelOfferId: selection.hotel.id,
          carOfferId: selection.car.id,
          passengers: selection.passengers,
          rooms: selection.rooms,
          idempotencyKey,
          simulateFailureAt: failure,
        },
      },
    }).catch(() => null);
    const order = result?.data?.bookPackage.order;
    if (order) {
      clearSelection();
      navigate(`/orders/${order.id}`);
    }
  }

  return (
    <section className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-3 lg:col-span-2">
        <h1 className="text-2xl font-semibold">Checkout</h1>
        <div className="rounded-xl bg-white p-4 shadow"><FlightSummary flight={selection.flight} /></div>
        <div className="rounded-xl bg-white p-4 shadow"><HotelSummary hotel={selection.hotel} /></div>
        <div className="rounded-xl bg-white p-4 shadow"><CarSummary car={selection.car} /></div>
        <p className="text-sm text-slate-500">
          {selection.passengers} pasajero(s) · {selection.rooms} habitación(es). El precio final lo fija cada servicio al reservar.
        </p>
      </div>

      <aside className="space-y-4">
        <div className="rounded-xl border-2 border-dashed border-amber-400 bg-amber-50 p-4">
          <h2 className="font-medium">Panel de demo · Simular fallo en</h2>
          <p className="mb-2 text-xs text-amber-800">Activa la compensación automática de la SAGA (requiere ENABLE_FAULT_INJECTION).</p>
          <div className="space-y-1">
            {FAILURE_OPTIONS.map((option) => (
              <label key={option.label} className="flex cursor-pointer gap-2 rounded-md p-1 text-sm hover:bg-amber-100">
                <input type="radio" name="failure" checked={failure === option.value} onChange={() => setFailure(option.value)} />
                <span>
                  <span className="font-medium">{option.label}</span>
                  <span className="block text-xs text-slate-600">{option.help}</span>
                </span>
              </label>
            ))}
          </div>
        </div>
        <div className="rounded-xl bg-white p-4 shadow">
          <p className="text-sm text-slate-500">Total estimado (sin impuestos)</p>
          <p className="text-2xl font-semibold">{money(estimate(selection))}</p>
          {error && <p className="mt-2 text-sm text-red-600">{errorMessage(error)}</p>}
          <button onClick={handlePay} disabled={loading}
                  className="mt-3 w-full rounded-md bg-emerald-600 py-2 font-medium text-white hover:bg-emerald-700 disabled:opacity-50">
            {loading ? "Reservando…" : "Confirmar y pagar"}
          </button>
        </div>
      </aside>
    </section>
  );
}
