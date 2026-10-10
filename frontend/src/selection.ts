import type { CarCardFragment, FlightCardFragment, HotelCardFragment } from "./gql/graphql";

// Selección del paquete entre el constructor y el checkout. Se guarda en sessionStorage para
// sobrevivir al desvío por /login; si el almacenamiento no está disponible, solo vive en memoria.
export type Selection = {
  flight: FlightCardFragment;
  hotel: HotelCardFragment;
  car: CarCardFragment;
  passengers: number;
  rooms: number;
};

const KEY = "wandersync:selection";
let memory: Selection | null = null;

export function saveSelection(selection: Selection): void {
  memory = selection;
  try {
    sessionStorage.setItem(KEY, JSON.stringify(selection));
  } catch {
    /* almacenamiento no disponible: queda en memoria */
  }
}

export function loadSelection(): Selection | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as Selection;
  } catch {
    /* ignorar */
  }
  return memory;
}

export function clearSelection(): void {
  memory = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignorar */
  }
}

/** Estimación con los precios del catálogo (el precio final lo fijan los servicios al reservar). */
export function estimate(selection: Selection): number {
  return (
    Number(selection.flight.price) * selection.passengers +
    Number(selection.hotel.priceTotal) * selection.rooms +
    Number(selection.car.priceTotal)
  );
}
