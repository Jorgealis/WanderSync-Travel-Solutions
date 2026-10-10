import { useParams } from "react-router";

// Esqueleto (3.10): la línea de tiempo de la SAGA (reservas y compensaciones) llega en la tarea 4.10.
export function OrderPage() {
  const { id } = useParams();
  return (
    <section className="rounded-xl bg-white p-6 shadow">
      <h1 className="text-xl font-semibold">Orden</h1>
      <p className="mt-2 font-mono text-sm text-slate-600">{id}</p>
      <p className="mt-2 text-slate-500">Aquí irá la línea de tiempo de la SAGA (tarea 4.10).</p>
    </section>
  );
}
