import { Scenarios } from "../../components/scenarios";
export default async function Page({ searchParams }: { searchParams: Promise<{ event?: string }> }) { const { event } = await searchParams; return <Scenarios initialEvent={event} />; }
