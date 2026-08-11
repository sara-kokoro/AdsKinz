import { createFileRoute, Navigate } from "@tanstack/react-router";
export const Route = createFileRoute("/kingcey/")({
  head: () => ({
    meta: [
      { title: "Admin — AdsKinz kingcey" },
      { name: "description", content: "Internal AdsKinz moderation and finance console." },
      { property: "og:title", content: "Admin — AdsKinz kingcey" },
      { property: "og:description", content: "Internal console for moderation, payouts and anomalies." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: () => <Navigate to="/kingcey/overview" />,
});
