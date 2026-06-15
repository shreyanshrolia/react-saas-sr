import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/src/contexts/AuthContext";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import type { Role } from "@/src/api/client";

export default function SignupScreen() {
  const { signup } = useAuth();
  const { t, lang, setLang } = useI18n();
  const router = useRouter();

  const [role, setRole] = useState<Role>("iron_man");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [address, setAddress] = useState("");
  const [securityQ, setSecurityQ] = useState("What is your favorite city?");
  const [securityA, setSecurityA] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const SECURITY_QS = [
    "What is your mother's maiden name?",
    "What was the name of your first school?",
    "What is your favorite city?",
    "What is your pet's name?",
    "Who was your childhood best friend?",
  ];

  const submit = async () => {
    setErr("");
    if (!name.trim()) return setErr(t("name"));
    if (phone.length !== 10) return setErr(t("phone_help"));
    if (password.length < 6) return setErr(t("password_help"));
    if (!securityA.trim()) return setErr("Please answer the security question");
    setLoading(true);
    try {
      const user = await signup({
        name: name.trim(), phone, password, role,
        address: address.trim() || undefined,
        security_question: securityQ,
        security_answer: securityA.trim(),
      } as any);
      if (user.role === "iron_man") router.replace("/(iron)/clients");
      else router.replace("/(client)/home");
    } catch (e: any) {
      setErr(e?.message || t("error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
          <View style={styles.topRow}>
            <TouchableOpacity testID="back-button" onPress={() => router.back()} style={styles.iconBtn}>
              <Ionicons name="chevron-back" size={22} color={colors.text} />
            </TouchableOpacity>
            <Pressable testID="lang-toggle" style={styles.langPill} onPress={() => setLang(lang === "en" ? "hi" : "en")}>
              <Ionicons name="language-outline" size={16} color={colors.primary} />
              <Text style={styles.langText}>{lang === "en" ? "हिंदी" : "English"}</Text>
            </Pressable>
          </View>

          <Text style={styles.heading}>{t("create_account")}</Text>
          <Text style={styles.subheading}>{t("tagline")}</Text>

          <Text style={styles.label}>{t("role")}</Text>
          <View style={styles.roleRow}>
            <TouchableOpacity
              testID="role-iron-man"
              style={[styles.roleCard, role === "iron_man" && styles.roleCardActive]}
              onPress={() => setRole("iron_man")}
              activeOpacity={0.85}
            >
              <View style={[styles.roleIcon, role === "iron_man" && styles.roleIconActive]}>
                <Ionicons name="hammer-outline" size={22} color={role === "iron_man" ? colors.textInverse : colors.primary} />
              </View>
              <Text style={[styles.roleTitle, role === "iron_man" && styles.roleTitleActive]}>{t("iron_man")}</Text>
              <Text style={styles.roleDesc}>{t("i_am_iron_man")}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="role-client"
              style={[styles.roleCard, role === "client" && styles.roleCardActive]}
              onPress={() => setRole("client")}
              activeOpacity={0.85}
            >
              <View style={[styles.roleIcon, role === "client" && styles.roleIconActive]}>
                <Ionicons name="home-outline" size={22} color={role === "client" ? colors.textInverse : colors.primary} />
              </View>
              <Text style={[styles.roleTitle, role === "client" && styles.roleTitleActive]}>{t("client")}</Text>
              <Text style={styles.roleDesc}>{t("i_am_client")}</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>{t("name")}</Text>
            <TextInput
              testID="signup-name-input"
              style={styles.input}
              placeholder={t("name")}
              placeholderTextColor={colors.textMuted}
              value={name}
              onChangeText={setName}
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>{t("phone")}</Text>
            <View style={styles.inputRow}>
              <Text style={styles.prefix}>+91</Text>
              <TextInput
                testID="signup-phone-input"
                style={[styles.input, styles.inputInline]}
                placeholder="9876543210"
                placeholderTextColor={colors.textMuted}
                keyboardType="phone-pad"
                maxLength={10}
                value={phone}
                onChangeText={(v) => setPhone(v.replace(/\D/g, ""))}
              />
            </View>
            <Text style={styles.help}>{t("phone_help")}</Text>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>{t("password")}</Text>
            <TextInput
              testID="signup-password-input"
              style={styles.input}
              placeholder="••••••"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />
            <Text style={styles.help}>{t("password_help")}</Text>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>{t("address")}</Text>
            <TextInput
              testID="signup-address-input"
              style={[styles.input, { height: 80, textAlignVertical: "top", paddingTop: 14 }]}
              placeholder={t("address")}
              placeholderTextColor={colors.textMuted}
              multiline
              value={address}
              onChangeText={setAddress}
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>Security Question (for password reset)</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
              {SECURITY_QS.map((q) => (
                <TouchableOpacity
                  key={q}
                  testID={`sec-q-${q.slice(0, 10)}`}
                  onPress={() => setSecurityQ(q)}
                  style={{
                    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999,
                    backgroundColor: securityQ === q ? colors.primary : colors.card,
                    borderWidth: 1, borderColor: securityQ === q ? colors.primary : colors.border,
                  }}
                >
                  <Text style={{ fontSize: 11, fontWeight: "600", color: securityQ === q ? colors.textInverse : colors.textSecondary }}>{q}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput
              testID="signup-security-answer-input"
              style={[styles.input, { marginTop: 8 }]}
              placeholder="Your answer (case-insensitive)"
              placeholderTextColor={colors.textMuted}
              value={securityA}
              onChangeText={setSecurityA}
              autoCapitalize="none"
            />
            <Text style={styles.help}>You'll need this to reset your password.</Text>
          </View>

          {err ? <Text style={styles.error}>{err}</Text> : null}

          <TouchableOpacity
            testID="signup-submit-button"
            style={[styles.primaryBtn, loading && styles.btnDisabled]}
            onPress={submit}
            disabled={loading}
          >
            {loading ? <ActivityIndicator color={colors.textInverse} /> : <Text style={styles.primaryBtnText}>{t("create_account")}</Text>}
          </TouchableOpacity>

          <View style={styles.switchRow}>
            <Text style={styles.switchText}>{t("have_account")} </Text>
            <TouchableOpacity testID="go-login-link" onPress={() => router.replace("/(auth)/login")}>
              <Text style={styles.switchLink}>{t("login_now")}</Text>
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
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  iconBtn: {
    width: 40, height: 40, borderRadius: radius.lg, alignItems: "center", justifyContent: "center",
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  langPill: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingHorizontal: spacing.md, paddingVertical: 6,
    backgroundColor: colors.card, borderRadius: radius.pill,
    borderWidth: 1, borderColor: colors.border,
  },
  langText: { color: colors.primary, fontWeight: "600", fontSize: 13 },
  heading: { fontSize: 28, fontWeight: "800", color: colors.text, marginTop: spacing.xl },
  subheading: { fontSize: 14, color: colors.textSecondary, marginTop: 4, marginBottom: spacing.xl },
  label: {
    fontSize: 12, fontWeight: "600", color: colors.textSecondary,
    marginBottom: 8, letterSpacing: 0.5, textTransform: "uppercase",
  },
  roleRow: { flexDirection: "row", gap: spacing.md, marginBottom: spacing.lg },
  roleCard: {
    flex: 1, backgroundColor: colors.card, borderRadius: radius.lg,
    padding: spacing.lg, borderWidth: 1, borderColor: colors.border,
  },
  roleCardActive: { borderColor: colors.primary, borderWidth: 2, backgroundColor: "#EEF2FF" },
  roleIcon: {
    width: 40, height: 40, borderRadius: radius.md,
    backgroundColor: colors.bgSecondary, alignItems: "center", justifyContent: "center", marginBottom: 10,
  },
  roleIconActive: { backgroundColor: colors.primary },
  roleTitle: { fontSize: 15, fontWeight: "700", color: colors.text },
  roleTitleActive: { color: colors.primary },
  roleDesc: { fontSize: 11, color: colors.textSecondary, marginTop: 4 },
  field: { marginBottom: spacing.lg },
  inputRow: {
    flexDirection: "row", alignItems: "center", backgroundColor: colors.inputBg,
    borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.lg, height: 52,
  },
  prefix: { color: colors.textSecondary, fontSize: 16, marginRight: 8, fontWeight: "500" },
  input: {
    backgroundColor: colors.inputBg, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border,
    paddingHorizontal: spacing.lg, height: 52, fontSize: 16, color: colors.text,
  },
  inputInline: { flex: 1, backgroundColor: "transparent", borderWidth: 0, paddingHorizontal: 0, height: 52 },
  help: { fontSize: 12, color: colors.textMuted, marginTop: 6 },
  error: { color: colors.danger, fontSize: 13, marginBottom: spacing.sm, textAlign: "center" },
  primaryBtn: {
    backgroundColor: colors.primary, borderRadius: radius.lg, height: 52,
    alignItems: "center", justifyContent: "center", marginTop: spacing.md,
  },
  btnDisabled: { opacity: 0.7 },
  primaryBtnText: { color: colors.textInverse, fontSize: 16, fontWeight: "700", letterSpacing: 0.3 },
  switchRow: { flexDirection: "row", justifyContent: "center", marginTop: spacing.xl },
  switchText: { color: colors.textSecondary, fontSize: 14 },
  switchLink: { color: colors.primary, fontSize: 14, fontWeight: "700" },
});
