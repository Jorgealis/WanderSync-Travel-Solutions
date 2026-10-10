import { CITIES, duration, money, time } from "../format";
import type { CarCardFragment, FlightCardFragment, HotelCardFragment } from "../gql/graphql";

const CATEGORY: Record<string, string> = { ECONOMY: "Económico", COMPACT: "Compacto", SUV: "SUV", VAN: "Van", LUXURY: "Lujo" };

export function FlightSummary({ flight }: { flight: FlightCardFragment }) {
  return (
    <div>
      <p className="font-medium">
        {flight.airline} · {time(flight.departureAt)} → {time(flight.arrivalAt)}
      </p>
      <p className="text-sm text-slate-500">
        {CITIES[flight.origin] ?? flight.origin} → {CITIES[flight.destination] ?? flight.destination} · {duration(flight.durationMinutes)} ·{" "}
        {flight.stops === 0 ? "Directo" : `${flight.stops} escala${flight.stops > 1 ? "s" : ""}`}
        {flight.operatedBy && flight.operatedBy !== flight.airline ? ` · opera ${flight.operatedBy}` : ""}
      </p>
      <p className="text-sm">
        <span className="font-semibold">{money(flight.price)}</span>
        <span className="text-slate-500"> por pasajero · desde {money(flight.originalPrice, flight.originalCurrency)}</span>
      </p>
    </div>
  );
}

export function HotelSummary({ hotel }: { hotel: HotelCardFragment }) {
  return (
    <div>
      <p className="font-medium">
        {hotel.hotelName} {hotel.stars ? <span className="text-amber-500">{"★".repeat(hotel.stars)}</span> : <span className="text-xs text-slate-500">{hotel.categoryName}</span>}
      </p>
      <p className="text-sm text-slate-500">
        {hotel.roomName} · {hotel.boardName.toLowerCase()} · {hotel.zoneName}
      </p>
      <p className="text-sm">
        <span className="font-semibold">{money(hotel.priceTotal)}</span>
        <span className="text-slate-500"> por {hotel.nights} noches ({money(hotel.pricePerNight)}/noche) · {hotel.roomsAvailable} disp.</span>
      </p>
    </div>
  );
}

export function CarSummary({ car }: { car: CarCardFragment }) {
  return (
    <div>
      <p className="font-medium">
        {car.model} <span className="text-sm font-normal text-slate-500">o similar</span>
      </p>
      <p className="text-sm text-slate-500">
        {car.company} · {CATEGORY[car.category] ?? car.category} · {car.transmission === "AUTOMATIC" ? "Automático" : "Manual"} · {car.seats} puestos
      </p>
      <p className="text-sm">
        <span className="font-semibold">{money(car.priceTotal)}</span>
        <span className="text-slate-500"> por {car.days} días ({money(car.pricePerDay)}/día)</span>
      </p>
    </div>
  );
}
