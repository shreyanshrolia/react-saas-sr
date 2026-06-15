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

export default function LoginScreen() {
  const { login } = useAuth();
  const { t, lang, setLang } = useI18n();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr("");
    if (phone.length !== 10) {
      setErr(t("phone_help"));
      return;
    }
    if (password.length < 6) {
      setErr(t("password_help"));
      return;
    }
    setLoading(true);
    try {
      const user = await login(phone, password);
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
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.langRow}>
            <Pressable
              testID="lang-toggle"
              style={styles.langPill}
              onPress={() => setLang(lang === "en" ? "hi" : "en")}
            >
              <Ionicons name="language-outline" size={16} color={colors.primary} />
              <Text style={styles.langText}>{lang === "en" ? "हिंदी" : "English"}</Text>
            </Pressable>
          </View>

          <View style={styles.brandWrap}>
            <Pressable
              testID="admin-entry"
              onLongPress={() => router.push("/(admin)/login")}
              delayLongPress={1200}
              style={styles.logo}
            >
              <Ionicons name="shirt" size={36} color={colors.textInverse} />
            </Pressable>
            <Text style={styles.brand}>{t("app_name")}</Text>
            <Text style={styles.tagline}>{t("tagline")}</Text>
          </View>

          <Text style={styles.heading}>{t("welcome_back")}</Text>

          <View style={styles.field}>
            <Text style={styles.label}>{t("phone")}</Text>
            <View style={styles.inputRow}>
              <Text style={styles.prefix}>+91</Text>
              <TextInput
                testID="login-phone-input"
                style={styles.input}
                placeholder="9876543210"
                placeholderTextColor={colors.textMuted}
                keyboardType="phone-pad"
                maxLength={10}
                value={phone}
                onChangeText={(v) => setPhone(v.replace(/\D/g, ""))}
              />
            </View>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>{t("password")}</Text>
            <View style={styles.inputRow}>
              <TextInput
                testID="login-password-input"
                style={styles.input}
                placeholder="••••••"
                placeholderTextColor={colors.textMuted}
                secureTextEntry={!showPw}
                value={password}
                onChangeText={setPassword}
              />
              <TouchableOpacity onPress={() => setShowPw(!showPw)} style={styles.eyeBtn}>
                <Ionicons
                  name={showPw ? "eye-off-outline" : "eye-outline"}
                  size={20}
                  color={colors.textMuted}
                />
              </TouchableOpacity>
            </View>
          </View>

          {err ? <Text style={styles.error}>{err}</Text> : null}

          <TouchableOpacity
            testID="login-submit-button"
            style={[styles.primaryBtn, loading && styles.btnDisabled]}
            onPress={submit}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color={colors.textInverse} />
            ) : (
              <Text style={styles.primaryBtnText}>{t("login")}</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            testID="forgot-password-link"
            onPress={() => router.push("/(auth)/forgot-password")}
            style={{ alignItems: "center", marginTop: spacing.md }}
          >
            <Text style={[styles.switchLink, { fontSize: 13 }]}>Forgot password?</Text>
          </TouchableOpacity>

          <View style={styles.switchRow}>
            <Text style={styles.switchText}>{t("no_account")} </Text>
            <TouchableOpacity
              testID="go-signup-link"
              onPress={() => router.push("/(auth)/signup")}
            >
              <Text style={styles.switchLink}>{t("signup_now")}</Text>
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
  langRow: { alignItems: "flex-end" },
  langPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    backgroundColor: colors.card,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  langText: { color: colors.primary, fontWeight: "600", fontSize: 13 },
  brandWrap: { alignItems: "center", marginTop: spacing.xl, marginBottom: spacing.xxxl },
  logo: {
    width: 72,
    height: 72,
    borderRadius: radius.xl,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
    shadowColor: colors.primary,
    shadowOpacity: 0.2,
    shadowOffset: { width: 0, height: 8 },
    shadowRadius: 16,
    elevation: 6,
  },
  brand: { fontSize: 32, fontWeight: "800", color: colors.text, letterSpacing: 0.5 },
  tagline: { fontSize: 14, color: colors.textSecondary, marginTop: 4 },
  heading: { fontSize: 22, fontWeight: "700", color: colors.text, marginBottom: spacing.xl },
  field: { marginBottom: spacing.lg },
  label: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: 8,
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.inputBg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.lg,
    height: 52,
  },
  prefix: { color: colors.textSecondary, fontSize: 16, marginRight: 8, fontWeight: "500" },
  input: { flex: 1, fontSize: 16, color: colors.text, height: 52 },
  eyeBtn: { padding: 4 },
  error: {
    color: colors.danger,
    fontSize: 13,
    marginBottom: spacing.sm,
    textAlign: "center",
  },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.lg,
    shadowColor: colors.primary,
    shadowOpacity: 0.25,
    shadowOffset: { width: 0, height: 6 },
    shadowRadius: 12,
    elevation: 4,
  },
  btnDisabled: { opacity: 0.7 },
  primaryBtnText: {
    color: colors.textInverse,
    fontSize: 16,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  switchRow: {
    flexDirection: "row",
    justifyContent: "center",
    marginTop: spacing.xl,
  },
  switchText: { color: colors.textSecondary, fontSize: 14 },
  switchLink: { color: colors.primary, fontSize: 14, fontWeight: "700" },
});
