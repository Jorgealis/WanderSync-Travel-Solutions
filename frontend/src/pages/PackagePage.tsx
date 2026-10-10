import { useQuery } from "@apollo/client/react";
import { type ReactNode, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { CarSummary, FlightSummary, HotelSummary } from "../components/OfferCards";
import { errorMessage } from "../errors";
import { addDays, CITIES, money } from "../format";
import { SEARCH_OFFERS } from "../graphql/operations";
import { estimate, saveSelection } from "../selection";

/** Constructor de paquetes (tarea 4.8): vuelo + hotel + auto, con sugerencias del gateway. */
export function PackagePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const origin = params.get("origin") ?? "BOG";
  const destination = params.get("destination") ?? "MDE";
  const departure = params.get("departure") ?? "";
  const nights = Number(params.get("nights") ?? 3);
  const passengers = Number(params.get("passengers") ?? 1);
  const rooms = Number(params.get("rooms") ?? 1);
  const returnDate = departure ? addDays(departure, nights) : "";

  const { data, loading, error } = useQuery(SEARCH_OFFERS, {
    skip: !departure,
    variables: {
      flights: { origin, destination, departureDate: departure, passengers, limit: 15 },
      hotels: {
        cityCode: destination, checkIn: departure, checkOut: returnDate,
        guests: Math.ceil(passengers / rooms), rooms, limit: 15,
      },
      cars: { cityCode: destination, pickupDate: departure, dropoffDate: returnDate, limit: 15 },
      packages: { origin, destination, departureDate: departure, returnDate, passengers, rooms, limit: 3 },
    },
  });

  const [flightId, setFlightId] = useState<string | null>(null);
  const [hotelId, setHotelId] = useState<string | null>(null);
  const [carId, setCarId] = useState<string | null>(null);

  // Una oferta de un paquete sugerido puede no estar entre las primeras de cada lista.
  const packages = data?.packages ?? [];
  const flight = [...(data?.flights ?? []), ...packages.map((p) => p.flight)].find((f) => f.id === flightId);
  const hotel = [...(data?.hotels ?? []), ...packages.map((p) => p.hotel)].find((h) => h.id === hotelId);
  const car = [...(data?.cars ?? []), ...packages.map((p) => p.car)].find((c) => c.id === carId);
  const complete = flight && hotel && car;

  function choosePackage(ids: { flight: string; hotel: string; car: string }) {
    setFlightId(ids.flight);
    setHotelId(ids.hotel);
    setCarId(ids.car);
  }

  function goToCheckout() {
    if (!complete) return;
    saveSelection({ flight, hotel, car, passengers, rooms });
    navigate("/checkout");
  }

  const heading = `${CITIES[origin] ?? origin} → ${CITIES[destination] ?? destination}`;
  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">{heading}</h1>
          <p className="text-sm text-slate-500">
            {departure} → {returnDate} · {nights} noches · {passengers} pasajero(s) · {rooms} habitación(es)
          </p>
        </div>
        <Link to="/search" className="text-sm text-sky-700 underline">Cambiar búsqueda</Link>
      </div>

      {loading && <p className="text-slate-500">Buscando ofertas…</p>}
      {error && <p className="text-red-600">{errorMessage(error)}</p>}

      {data && (
        <>
          {data.packages.length > 0 && (
            <div className="rounded-xl bg-sky-50 p-4">
              <h2 className="mb-2 font-medium">Paquetes sugeridos</h2>
              <div className="grid gap-2 sm:grid-cols-3">
                {data.packages.map((pkg, index) => {
                  const selected = flightId === pkg.flight.id && hotelId === pkg.hotel.id && carId === pkg.car.id;
                  return (
                    <button key={index} type="button"
                            onClick={() => choosePackage({ flight: pkg.flight.id, hotel: pkg.hotel.id, car: pkg.car.id })}
                            className={`rounded-lg border bg-white p-3 text-left ${selected ? "border-sky-600 ring-2 ring-sky-200" : "border-slate-200"}`}>
                      <p className="text-sm text-slate-500">Opción {index + 1}</p>
                      <p className="text-lg font-semibold">{money(pkg.estimatedPrice.total)}</p>
                      <p className="text-xs text-slate-500">impuestos estimados incluidos</p>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-3">
            <Column title="1. Vuelo" empty={data.flights.length === 0}>
              {data.flights.map((f) => (
                <Option key={f.id} selected={f.id === flightId} onSelect={() => setFlightId(f.id)}><FlightSummary flight={f} /></Option>
              ))}
            </Column>
            <Column title="2. Hotel" empty={data.hotels.length === 0}>
              {data.hotels.map((h) => (
                <Option key={h.id} selected={h.id === hotelId} onSelect={() => setHotelId(h.id)}><HotelSummary hotel={h} /></Option>
              ))}
            </Column>
            <Column title="3. Auto" empty={data.cars.length === 0}>
              {data.cars.map((c) => (
                <Option key={c.id} selected={c.id === carId} onSelect={() => setCarId(c.id)}><CarSummary car={c} /></Option>
              ))}
            </Column>
          </div>

          <div className="sticky bottom-4 flex items-center justify-between rounded-xl bg-white p-4 shadow-lg">
            <p className="text-sm">
              {complete ? (
                <>Total estimado (sin impuestos): <span className="text-lg font-semibold">{money(estimate({ flight, hotel, car, passengers, rooms }))}</span></>
              ) : (
                <span className="text-slate-500">Elige un vuelo, un hotel y un auto, o toma un paquete sugerido.</span>
              )}
            </p>
            <button disabled={!complete} onClick={goToCheckout}
                    className="rounded-md bg-sky-700 px-5 py-2 font-medium text-white hover:bg-sky-800 disabled:opacity-40">
              Continuar al checkout
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function Column({ title, empty, children }: { title: string; empty: boolean; children: ReactNode }) {
  return (
    <div>
      <h2 className="mb-2 font-medium">{title}</h2>
      {empty ? (
        <p className="rounded-lg bg-white p-4 text-sm text-slate-500 shadow">Sin ofertas para estas fechas. Prueba con otra fecha de la búsqueda.</p>
      ) : (
        <div className="max-h-[32rem] space-y-2 overflow-y-auto pr-1">{children}</div>
      )}
    </div>
  );
}

function Option({ selected, onSelect, children }: { selected: boolean; onSelect: () => void; children: ReactNode }) {
  return (
    <button type="button" onClick={onSelect}
            className={`block w-full rounded-lg border bg-white p-3 text-left shadow-sm ${selected ? "border-sky-600 ring-2 ring-sky-200" : "border-slate-200 hover:border-slate-300"}`}>
      {children}
    </button>
  );
}
