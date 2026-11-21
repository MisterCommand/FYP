import { Runs } from "../../components/runs";
export default async function Page({ searchParams }: { searchParams: Promise<{ q?: string | string[] }> }) {
  const { q } = await searchParams;
  return <Runs initialQuery={Array.isArray(q) ? q[0] : q} />;
}
