import { useQuery } from "@apollo/client/react";

import { errorMessage } from "../errors";
import { CATALOG_STATUS } from "../graphql/operations";

const LABELS: Record<string, string> = { flights: "Vuelos", hotels: "Hoteles", cars: "Autos" };

// Esqueleto (3.10): muestra el estado real del catálogo para comprobar Apollo → gateway → Hasura.
// La búsqueda y el constructor de paquetes llegan en la tarea 4.8; el indicador de
// "última sincronización" de esta tabla es la base de la 4.11.
export function SearchPage() {
  const { data, loading, error } = useQuery(CATALOG_STATUS);

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Arma tu paquete de viaje</h1>
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
              {data.catalogStatus.map((source) => (
                <tr key={source.catalog} className="border-t border-slate-100">
                  <td className="py-2">{LABELS[source.catalog] ?? source.catalog}</td>
                  <td>{source.totalOffers.toLocaleString("es-CO")}</td>
                  <td>{source.lastSyncAt ? new Date(source.lastSyncAt).toLocaleString("es-CO") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-sm text-slate-500">La búsqueda de vuelos, hoteles y autos se construye en la tarea 4.8.</p>
    </section>
  );
}
