import { ApiStatus } from "@/components/api-status";
import { LearnerExperience } from "@/components/learner-experience";
import { fetchApiHealth } from "@/lib/api";

export default async function Home() {
  const health = await fetchApiHealth().catch(() => null);

  return (
    <main className="min-h-screen bg-dawn-mist text-dawn-ink">
      <LearnerExperience />
      <aside className="mx-auto max-w-6xl px-5 pb-10 sm:px-8">
        <div className="max-w-md">
          <ApiStatus health={health} />
        </div>
      </aside>
    </main>
  );
}

