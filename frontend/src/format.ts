// Formato para la interfaz (es-CO). El backend entrega dinero como string decimal en USD.
const usd = new Intl.NumberFormat("es-CO", { style: "currency", currency: "USD" });

export function money(value: string | number | null | undefined, currency = "USD"): string {
  if (value === null || value === undefined) return "—";
  const amount = Number(value);
  if (currency === "USD") return usd.format(amount);
  return new Intl.NumberFormat("es-CO", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

export function dateTime(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }) : "—";
}

export function time(iso: string): string {
  // Los aeropuertos del proyecto están en Colombia: se muestra la hora local de Bogotá.
  return new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", timeZone: "America/Bogota" });
}

export function duration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h} h ${m ? `${m} min` : ""}`.trim() : `${m} min`;
}

export function relative(iso: string | null | undefined): string {
  if (!iso) return "sin datos";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "hace un momento";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `hace ${hours} h` : `hace ${Math.round(hours / 24)} días`;
}

/** Fechas en UTC: la ingesta calcula "hoy + N días" con la fecha UTC del servidor. */
export function utcDate(offsetDays: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export const CITIES: Record<string, string> = {
  BOG: "Bogotá",
  MDE: "Medellín",
  CTG: "Cartagena",
  SMR: "Santa Marta",
  ADZ: "San Andrés",
  CLO: "Cali",
};
