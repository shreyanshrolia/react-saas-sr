import { useState } from "react";
import {
  ActivityIndicator, KeyboardAvoidingView, Linking, Platform, ScrollView,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, setToken, type AuthResp } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";
import { colors, radius, spacing } from "@/src/theme/colors";

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [step, setStep] = useState<"phone" | "answer">("phone");
  const [phone, setPhone] = useState("");
  const [question, setQuestion] = useState("");
  const [name, setName] = useState("");
  const [answer, setAnswer] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const lookup = async () => {
    setErr("");
    if (phone.length !== 10) return setErr("Enter 10-digit phone");
    setLoading(true);
    try {
      const r = await api.post<{ phone: string; name: string; security_question: string }>(
        "/auth/forgot-password", { phone },
      );
      setQuestion(r.security_question);
      setName(r.name);
      setStep("answer");
    } catch (e: any) {
      setErr(e?.message || "Phone not found. Call helpline +91 63521 72550.");
    } finally { setLoading(false); }
  };

  const reset = async () => {
    setErr("");
    if (!answer.trim()) return setErr("Enter your answer");
    if (newPassword.length < 6) return setErr("Password must be 6+ characters");
    setLoading(true);
    try {
      const r = await api.post<AuthResp>("/auth/reset-password", {
        phone, security_answer: answer.trim(), new_password: newPassword,
      });
      await setToken(r.token);
      await refresh();
      if (r.user.role === "iron_man") router.replace("/(iron)/clients");
      else router.replace("/(client)/home");
    } catch (e: any) {
      setErr(e?.message || "Wrong answer. Call helpline.");
    } finally { setLoading(false); }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()} testID="back-button">
            <Ionicons name="chevron-back" size={22} color={colors.text} />
          </TouchableOpacity>

          <Text style={styles.title}>Reset password</Text>
          <Text style={styles.subtitle}>
            {step === "phone" ? "Enter your phone to begin" : `Hi ${name}, answer your security question`}
          </Text>

          {step === "phone" ? (
            <>
              <Text style={styles.label}>Phone</Text>
              <View style={styles.inputRow}>
                <Text style={styles.prefix}>+91</Text>
                <TextInput
                  testID="forgot-phone-input"
                  style={styles.inputInline}
                  value={phone}
                  onChangeText={(v) => setPhone(v.replace(/\D/g, ""))}
                  keyboardType="phone-pad"
                  maxLength={10}
                  placeholder="9876543210"
                  placeholderTextColor={colors.textMuted}
                />
              </View>

              {err ? <Text style={styles.error}>{err}</Text> : null}

              <TouchableOpacity testID="forgot-continue" style={styles.btn} onPress={lookup} disabled={loading}>
                {loading ? <ActivityIndicator color={colors.textInverse} /> : <Text style={styles.btnText}>Continue</Text>}
              </TouchableOpacity>
            </>
          ) : (
            <>
              <View style={styles.qBox}>
                <Ionicons name="help-circle" size={18} color={colors.primary} />
                <Text style={styles.qText}>{question}</Text>
              </View>

              <Text style={styles.label}>Your answer</Text>
              <TextInput
                testID="security-answer-input"
                style={styles.input}
                value={answer}
                onChangeText={setAnswer}
                placeholder="Type your answer"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="none"
              />

              <Text style={styles.label}>New password</Text>
              <TextInput
                testID="new-password-input"
                style={styles.input}
                value={newPassword}
                onChangeText={setNewPassword}
                placeholder="Min 6 characters"
                placeholderTextColor={colors.textMuted}
                secureTextEntry
              />

              {err ? <Text style={styles.error}>{err}</Text> : null}

              <TouchableOpacity testID="reset-submit" style={styles.btn} onPress={reset} disabled={loading}>
                {loading ? <ActivityIndicator color={colors.textInverse} /> : <Text style={styles.btnText}>Reset & log in</Text>}
              </TouchableOpacity>
            </>
          )}

          <View style={styles.helpline}>
            <Ionicons name="call" size={16} color={colors.success} />
            <Text style={styles.helplineText}>Stuck? Call helpline</Text>
            <TouchableOpacity testID="call-helpline" onPress={() => Linking.openURL("tel:6352172550")}>
              <Text style={styles.helplineNumber}>+91 63521 72550</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  scroll: { padding: spacing.xl, paddingBottom: spacing.xxxl, flexGrow: 1 },
  backBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg },
  title: { fontSize: 26, fontWeight: "800", color: colors.text },
  subtitle: { fontSize: 14, color: colors.textSecondary, marginTop: 4, marginBottom: spacing.xl },
  label: { fontSize: 12, fontWeight: "600", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5, marginTop: spacing.lg, marginBottom: 8 },
  inputRow: { flexDirection: "row", alignItems: "center", backgroundColor: colors.inputBg, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.lg, height: 52 },
  prefix: { color: colors.textSecondary, fontSize: 16, marginRight: 8, fontWeight: "500" },
  inputInline: { flex: 1, fontSize: 16, color: colors.text, height: 52 },
  input: { backgroundColor: colors.inputBg, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.lg, height: 52, fontSize: 16, color: colors.text },
  error: { color: colors.danger, fontSize: 13, marginTop: spacing.md, textAlign: "center" },
  btn: { marginTop: spacing.xl, height: 52, borderRadius: radius.lg, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  btnText: { color: colors.textInverse, fontSize: 16, fontWeight: "800" },
  qBox: { flexDirection: "row", alignItems: "center", gap: 8, padding: spacing.lg, backgroundColor: "#EEF2FF", borderRadius: radius.lg, marginTop: spacing.md },
  qText: { fontSize: 14, color: colors.primary, fontWeight: "700", flex: 1 },
  helpline: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, marginTop: spacing.xxxl, padding: spacing.md, backgroundColor: colors.successLight, borderRadius: radius.md },
  helplineText: { fontSize: 12, color: colors.success, fontWeight: "600" },
  helplineNumber: { fontSize: 13, color: colors.success, fontWeight: "800", textDecorationLine: "underline" },
});
