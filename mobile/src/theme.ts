// Site palette: steel + concrete, one hi-vis orange reserved for "needs you".
export const C = {
  steel: "#1F252C",
  slate: "#2E3844",
  slateLine: "#3C4856",
  concrete: "#ECEBE7",
  panel: "#FFFFFF",
  line: "#D9D7D1",
  ink: "#1F252C",
  muted: "#6C7480",
  onSteel: "#AEB8C4",
  hivis: "#F26B21",
  ok: "#2E8B57",
  bad: "#C23B2E",
  info: "#2F5F8F",
};

export const F = {
  display: "BarlowCondensed_700Bold",
  displayM: "BarlowCondensed_600SemiBold",
  body: "Barlow_400Regular",
  bodyM: "Barlow_500Medium",
  bodyB: "Barlow_600SemiBold",
};

export const R = 6; // steel-plate corners, not pill/bubble

export const statusColor = (s: string) =>
  s === "completed" ? C.ok : s === "under_bgcc_revision" ? C.bad : s === "under_drafting" ? C.muted : C.info;
