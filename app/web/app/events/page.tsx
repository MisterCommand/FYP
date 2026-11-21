import { Events } from "../../components/events";
export default async function Page({ searchParams }: { searchParams: Promise<{ q?: string | string[] }> }) {
  const { q } = await searchParams;
  return <Events initialQuery={Array.isArray(q) ? q[0] : q} />;
}
