import { useQuery } from "@apollo/client/react";

import { relative } from "../format";
import { CATALOG_STATUS } from "../graphql/operations";

const LABELS: Record<string, string> = { flights: "vuelos", hotels: "hoteles", cars: "autos" };

/** Indicador de "última sincronización de tarifas" (tarea 4.11): lee scraped_at del catálogo. */
export function LastSync() {
  const { data } = useQuery(CATALOG_STATUS, { pollInterval: 60_000 });
  if (!data) return null;
  return (
    <p className="text-xs text-sky-100" title="Momento de la última ingesta de cada catálogo (Prefect + Dask)">
      Tarifas actualizadas:{" "}
      {data.catalogStatus.map((s) => `${LABELS[s.catalog] ?? s.catalog} ${relative(s.lastSyncAt)}`).join(" · ")}
    </p>
  );
}
