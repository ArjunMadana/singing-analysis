import type { Metadata } from "next";
import { VocalLabApp } from "./VocalLabApp";

export const metadata: Metadata = {
  title: "VocalLab",
  description: "Private, local-first singing analysis and focused phrase practice.",
};

export default function Home() {
  return <VocalLabApp />;
}
