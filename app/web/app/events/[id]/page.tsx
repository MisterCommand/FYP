import { EventDetails } from "../../../components/events";
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ as_of?: string | string[] }> }) {
  const { id } = await params;
  const { as_of } = await searchParams;
  return <EventDetails id={id} asOf={Array.isArray(as_of) ? as_of[0] : as_of} />;
}
