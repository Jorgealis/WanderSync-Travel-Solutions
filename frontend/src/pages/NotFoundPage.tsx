import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <section className="text-center">
      <h1 className="text-xl font-semibold">Página no encontrada</h1>
      <Link to="/search" className="mt-3 inline-block text-sky-700 underline">Volver a la búsqueda</Link>
    </section>
  );
}
