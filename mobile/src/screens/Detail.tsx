import { useQuery } from "@tanstack/react-query";
import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";
import React, { useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { API_URL, api, errMsg, store } from "../api";
import { C, F } from "../theme";
import { Badge, Button, ErrorView, Panel, Scaffold, SkeletonList, Stage, fmtDate } from "../ui";
import type { Row } from "./Agreements";

type Step = { id: string; step_name: string; step_order: number; role_required: string; status: string; modified_since_approval?: boolean };
type Summary = {
  steps: Step[];
  comments: { id: string; comment_text: string; clause_reference: string | null; author_name: string | null; author_role: string | null; status: string; created_at: string | null }[];
};
type Fields = { fields: { field_id: string; field_label: string; clause_number: string; current_value: string }[] };

const SHORT: Record<string, string> = { accounts: "Accounts", project_director: "PD", operation_manager: "OM", gm: "GM" };

function chain(steps: Step[]): { stages: Stage[]; labels: string[]; stale: boolean } {
  const main = steps.filter((x) => !x.step_name.startsWith("Resolution")).sort((a, b) => a.step_order - b.step_order);
  let currentSet = false;
  const stages = main.map<Stage>((x) => {
    if (x.status === "approved") return "done";
    if (x.status === "returned") return "returned";
    if (!currentSet) return (currentSet = true), "current";
    return "todo";
  });
  return { stages, labels: main.map((x) => SHORT[x.role_required] ?? x.step_name), stale: main.some((x) => x.status === "approved" && x.modified_since_approval) };
}

const money = (v: string) => (isNaN(Number(v)) ? v : `AED ${Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 })}`);

export default function Detail({ route }: any) {
  const { id } = route.params as { id: string };
  const [busy, setBusy] = useState(false);
  const a = useQuery({ queryKey: ["agreement", id], queryFn: async () => (await api.get<Row>(`/archive/agreements/${id}`)).data });
  const w = useQuery({ queryKey: ["summary", id], queryFn: async () => (await api.get<Summary>(`/workflow/agreements/${id}`)).data });
  const f = useQuery({ queryKey: ["fields", id], queryFn: async () => (await api.get<Fields>(`/workflow/agreements/${id}/fields`)).data });

  if (a.isLoading) return <View style={{ flex: 1, backgroundColor: C.concrete }}><SkeletonList /></View>;
  if (a.isError || !a.data) return <ErrorView msg={errMsg(a.error)} retry={() => a.refetch()} />;
  const r = a.data;
  const ch = w.data ? chain(w.data.steps) : null;
  const resolution = (w.data?.steps ?? []).filter((x) => x.step_name.startsWith("Resolution"));

  const openPdf = async () => {
    setBusy(true);
    try {
      const token = await store.get("access");
      const dest = new File(Paths.cache, `${r.reference_number.replace(/[^\w-]/g, "_")}.pdf`);
      const file = await File.downloadFileAsync(`${API_URL}/pdf/${id}/preview`, dest, { headers: { Authorization: `Bearer ${token}` }, idempotent: true });
      await Sharing.shareAsync(file.uri, { mimeType: "application/pdf", dialogTitle: r.reference_number });
    } catch {
      Alert.alert("No PDF yet", "A PDF hasn't been generated for this agreement.");
    } finally {
      setBusy(false);
    }
  };

  const filled = (f.data?.fields ?? []).filter((x) => x.current_value.trim());
  const price = f.data?.fields.find((x) => x.field_id === "F08")?.current_value;

  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.concrete }} contentContainerStyle={{ paddingBottom: 32 }}>
      <View style={s.hero}>
        <Text style={s.ref}>{r.reference_number}</Text>
        <View style={{ marginTop: 8 }}><Badge onDark status={r.current_status} label={r.status_label} /></View>
        <Text style={s.pending}>{r.pending_with}</Text>
        <View style={{ marginTop: 18 }}>
          {ch ? <Scaffold large animate stages={ch.stages} labels={ch.labels} /> : <View style={{ height: 34 }} />}
        </View>
        {ch?.stale && <Text style={s.stale}>Edited since a reviewer approved. They've been asked to look again.</Text>}
        {!!price && <Text style={s.price}>{money(price)}</Text>}
      </View>

      <View style={{ padding: 12 }}>
        <View style={{ marginBottom: 12 }}><Button title={busy ? "Preparing PDF…" : "Open PDF"} onPress={openPdf} disabled={busy} /></View>

        <Panel title="Agreement">
          <Item k="Project" v={`${r.project_name ?? "—"}${r.project_code ? `  (${r.project_code})` : ""}`} />
          <Item k="Subcontractor" v={r.subcontractor_name ?? "—"} />
          {!!r.scope_of_works && <Item k="Scope of works" v={r.scope_of_works} />}
        </Panel>

        {resolution.length > 0 && (
          <Panel title="Comment resolution">
            {resolution.map((x) => <Item key={x.id} k={x.step_name.replace("Resolution - ", "")} v={x.status} />)}
          </Panel>
        )}

        <Panel title={`Comments  ${w.data?.comments.length ?? 0}`}>
          {w.data?.comments.length === 0 && <Text style={s.muted}>No comments yet.</Text>}
          {w.data?.comments.map((c) => (
            <View key={c.id} style={s.comment}>
              <Text style={s.who}>{c.author_name ?? "—"}<Text style={s.muted}>  {c.author_role?.replace("_", " ")}{c.clause_reference ? `  ·  ${c.clause_reference}` : ""}</Text></Text>
              <Text style={s.body}>{c.comment_text}</Text>
              <Text style={s.small}>{fmtDate(c.created_at)}  ·  {c.status}</Text>
            </View>
          ))}
        </Panel>

        <Panel title={`Entered details  ${filled.length}`}>
          {filled.length === 0 && <Text style={s.muted}>Nothing entered yet.</Text>}
          {filled.map((x) => <Item key={x.field_id} k={`${x.clause_number ? x.clause_number + "  " : ""}${x.field_label}`} v={x.current_value} />)}
        </Panel>
      </View>
    </ScrollView>
  );
}

const Item = ({ k, v }: { k: string; v: string }) => (
  <View style={{ marginTop: 10 }}>
    <Text style={s.k}>{k}</Text>
    <Text style={s.v}>{v}</Text>
  </View>
);

const s = StyleSheet.create({
  hero: { backgroundColor: C.steel, padding: 18, paddingTop: 8 },
  ref: { fontFamily: F.display, fontSize: 40, color: "#fff", letterSpacing: 0.3 },
  pending: { fontFamily: F.body, color: C.onSteel, marginTop: 8 },
  stale: { fontFamily: F.bodyM, color: C.hivis, marginTop: 14 },
  price: { fontFamily: F.displayM, fontSize: 26, color: "#fff", marginTop: 16 },
  k: { fontFamily: F.body, fontSize: 13, color: C.muted },
  v: { fontFamily: F.bodyM, fontSize: 16, color: C.ink, marginTop: 1 },
  muted: { fontFamily: F.body, color: C.muted },
  comment: { paddingVertical: 10, borderTopWidth: 1, borderColor: C.line },
  who: { fontFamily: F.bodyB, color: C.ink },
  body: { fontFamily: F.body, fontSize: 15, color: C.ink, marginTop: 3 },
  small: { fontFamily: F.body, fontSize: 12, color: C.muted, marginTop: 4 },
});
