import { useEffect, useState } from "react";
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

import { adminApi, getAdminToken, setAdminToken } from "@/src/api/admin";
import { colors, radius, spacing } from "@/src/theme/colors";

export default function AdminLoginScreen() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [bootChecking, setBootChecking] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      const existing = await getAdminToken();
      if (existing) {
        router.replace("/(admin)/dashboard");
        return;
      }
      setBootChecking(false);
    })();
  }, [router]);

  const submit = async () => {
    setErr("");
    if (!password.trim()) {
      setErr("Enter admin password");
      return;
    }
    setLoading(true);
    try {
      const res = await adminApi.login(password.trim());
      await setAdminToken(res.token);
      router.replace("/(admin)/dashboard");
    } catch (e: any) {
      setErr(e?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  if (bootChecking) {
    return (
      <SafeAreaView style={[styles.safe, styles.center]} edges={["top", "bottom"]}>
        <ActivityIndicator color={colors.primary} />
      </SafeAreaView>
    );
  }

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
          <View style={styles.topRow}>
            <Pressable
              testID="admin-back"
              onPress={() => router.replace("/(auth)/login")}
              style={styles.backBtn}
              hitSlop={12}
            >
              <Ionicons name="chevron-back" size={22} color={colors.text} />
              <Text style={styles.backText}>Back</Text>
            </Pressable>
          </View>

          <View style={styles.brandWrap}>
            <View style={styles.logo}>
              <Ionicons name="shield-checkmark" size={36} color={colors.textInverse} />
            </View>
            <Text style={styles.brand}>Admin Panel</Text>
            <Text style={styles.tagline}>Grihkari helpline support</Text>
          </View>

          <Text style={styles.heading}>Sign in</Text>

          <View style={styles.field}>
            <Text style={styles.label}>Admin password</Text>
            <View style={styles.inputRow}>
              <Ionicons name="lock-closed-outline" size={18} color={colors.textMuted} />
              <TextInput
                testID="admin-password-input"
                style={styles.input}
                placeholder="Enter admin password"
                placeholderTextColor={colors.textMuted}
                secureTextEntry={!showPw}
                value={password}
                onChangeText={setPassword}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <TouchableOpacity onPress={() => setShowPw(!showPw)} style={styles.eyeBtn} hitSlop={8}>
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
            testID="admin-login-submit"
            style={[styles.primaryBtn, loading && styles.btnDisabled]}
            onPress={submit}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color={colors.textInverse} />
            ) : (
              <Text style={styles.primaryBtnText}>Sign in</Text>
            )}
          </TouchableOpacity>

          <View style={styles.helperCard}>
            <Ionicons name="information-circle" size={16} color={colors.primary} />
            <Text style={styles.helperText}>
              Restricted access. Used only to reset passwords for users who call the helpline.
            </Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { alignItems: "center", justifyContent: "center" },
  scroll: { padding: spacing.xl, paddingBottom: spacing.xxxl, flexGrow: 1 },
  topRow: { flexDirection: "row", alignItems: "center" },
  backBtn: { flexDirection: "row", alignItems: "center", paddingVertical: 4 },
  backText: { color: colors.text, fontSize: 15, fontWeight: "600", marginLeft: 2 },
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
    shadowOpacity: 0.25,
    shadowOffset: { width: 0, height: 8 },
    shadowRadius: 16,
    elevation: 6,
  },
  brand: { fontSize: 28, fontWeight: "800", color: colors.text, letterSpacing: 0.5 },
  tagline: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
  heading: { fontSize: 20, fontWeight: "700", color: colors.text, marginBottom: spacing.xl },
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
    gap: 8,
  },
  input: { flex: 1, fontSize: 16, color: colors.text, height: 52 },
  eyeBtn: { padding: 4 },
  error: { color: colors.danger, fontSize: 13, marginBottom: spacing.sm, textAlign: "center" },
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
  primaryBtnText: { color: colors.textInverse, fontSize: 16, fontWeight: "700", letterSpacing: 0.3 },
  helperCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    marginTop: spacing.xl,
    padding: spacing.md,
    backgroundColor: colors.accentLight,
    borderRadius: radius.md,
  },
  helperText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
});
