import { useQuery } from "@apollo/client/react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";

import { errorMessage } from "../errors";
import { CITIES, dateTime, utcDate } from "../format";
import { CATALOG_STATUS } from "../graphql/operations";

const LABELS: Record<string, string> = { flights: "Vuelos", hotels: "Hoteles", cars: "Autos" };
// Fechas y duraciones que consulta la ingesta (INGEST_DATE_OFFSETS e INGEST_STAY_NIGHTS).
const QUICK_OFFSETS = [7, 14, 30];
const NIGHTS = [3, 5];
const field = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2";

/** Búsqueda (tarea 4.8): arma los parámetros y abre el constructor de paquetes. */
export function SearchPage() {
  const navigate = useNavigate();
  const { data, loading, error } = useQuery(CATALOG_STATUS);
  const [origin, setOrigin] = useState("BOG");
  const [destination, setDestination] = useState("MDE");
  const [departure, setDeparture] = useState(utcDate(7));
  const [nights, setNights] = useState(3);
  const [passengers, setPassengers] = useState(2);
  const [rooms, setRooms] = useState(1);

  function changeOrigin(code: string) {
    setOrigin(code);
    if (code === destination) setDestination(Object.keys(CITIES).find((c) => c !== code)!);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const params = new URLSearchParams({
      origin, destination, departure, nights: String(nights), passengers: String(passengers), rooms: String(rooms),
    });
    navigate(`/package?${params}`);
  }

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Arma tu paquete de viaje</h1>
      <form onSubmit={handleSubmit} className="grid gap-4 rounded-xl bg-white p-6 shadow sm:grid-cols-3">
        <label className="text-sm">
          Origen
          <select value={origin} onChange={(e) => changeOrigin(e.target.value)} className={field}>
            {Object.entries(CITIES).map(([code, name]) => (
              <option key={code} value={code}>{name} ({code})</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Destino
          <select value={destination} onChange={(e) => setDestination(e.target.value)} className={field}>
            {Object.entries(CITIES).filter(([code]) => code !== origin).map(([code, name]) => (
              <option key={code} value={code}>{name} ({code})</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Salida
          <input type="date" required value={departure} onChange={(e) => setDeparture(e.target.value)} className={field} />
        </label>
        <label className="text-sm">
          Estadía
          <select value={nights} onChange={(e) => setNights(Number(e.target.value))} className={field}>
            {NIGHTS.map((n) => <option key={n} value={n}>{n} noches</option>)}
          </select>
        </label>
        <label className="text-sm">
          Pasajeros
          <input type="number" min={1} max={9} value={passengers} onChange={(e) => setPassengers(Number(e.target.value))} className={field} />
        </label>
        <label className="text-sm">
          Habitaciones
          <input type="number" min={1} max={5} value={rooms} onChange={(e) => setRooms(Number(e.target.value))} className={field} />
        </label>
        <div className="flex flex-wrap items-center gap-2 text-sm sm:col-span-3">
          <span className="text-slate-500">Fechas con tarifas cargadas:</span>
          {QUICK_OFFSETS.map((offset) => {
            const day = utcDate(offset);
            return (
              <button key={offset} type="button" onClick={() => setDeparture(day)}
                      className={`rounded-full border px-3 py-1 ${departure === day ? "border-sky-600 bg-sky-50 text-sky-700" : "border-slate-300"}`}>
                {day}
              </button>
            );
          })}
          <button className="ml-auto rounded-md bg-sky-700 px-5 py-2 font-medium text-white hover:bg-sky-800">Buscar</button>
        </div>
      </form>

      <div className="rounded-xl bg-white p-6 shadow">
        <h2 className="mb-3 font-medium">Catálogo disponible</h2>
        {loading && <p className="text-slate-500">Cargando…</p>}
        {error && <p className="text-red-600">{errorMessage(error)}</p>}
        {data && (
          <table className="w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr><th className="py-1">Catálogo</th><th>Ofertas</th><th>Última sincronización</th></tr>
            </thead>
            <tbody>
              {data.catalogStatus.map((s) => (
                <tr key={s.catalog} className="border-t border-slate-100">
                  <td className="py-2">{LABELS[s.catalog] ?? s.catalog}</td>
                  <td>{s.totalOffers.toLocaleString("es-CO")}</td>
                  <td>{dateTime(s.lastSyncAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
