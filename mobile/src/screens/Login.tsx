import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { errMsg } from "../api";
import { useAuth } from "../auth";
import { C, F, R } from "../theme";
import { Button, Field } from "../ui";

/** Four rising storeys: the logo and the approval chain in one shape. */
const Mark = () => (
  <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 4 }}>
    {[22, 34, 46, 58].map((h, i) => <View key={h} style={{ width: 14, height: h, backgroundColor: i === 3 ? C.hivis : "#fff", borderRadius: 2 }} />)}
  </View>
);

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      await login(email, password);
    } catch (e) {
      const m = errMsg(e);
      setErr(m === "Invalid email or password" ? "Email or password is incorrect." : m);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={s.wrap}>
      <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
        <Mark />
        <Text style={s.brand}>Bhatia General Contracting</Text>
        <Text style={s.title}>SAMS</Text>
        <Text style={s.sub}>Subcontract agreements, wherever you are.</Text>
        <View style={s.form}>
          <Field placeholder="Work email" autoCapitalize="none" keyboardType="email-address" autoComplete="email" value={email} onChangeText={setEmail} />
          <Field placeholder="Password" secureTextEntry autoComplete="password" value={password} onChangeText={setPassword} onSubmitEditing={submit} />
          {!!err && <Text style={s.err}>{err}</Text>}
          <Button tone="light" title={busy ? "Signing in…" : "Sign in"} onPress={submit} disabled={busy || !email || !password} />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: C.steel },
  scroll: { flexGrow: 1, justifyContent: "center", padding: 28 },
  brand: { color: C.onSteel, fontFamily: F.bodyM, marginTop: 22, fontSize: 15 },
  title: { color: "#fff", fontFamily: F.display, fontSize: 72, lineHeight: 74, letterSpacing: 1 },
  sub: { color: C.onSteel, fontFamily: F.body, fontSize: 16, marginBottom: 32 },
  form: { gap: 12 },
  err: { color: "#FF8A7D", fontFamily: F.bodyM },
});
