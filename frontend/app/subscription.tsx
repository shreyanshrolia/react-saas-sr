import { useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type User } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { daysUntil, formatDate } from "@/src/utils/format";
import Toast from "@/src/components/Toast";

const PLANS = {
  iron_man: 49,
  client: 19,
} as const;

export default function SubscriptionScreen() {
  const { user, refresh } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; variant?: "success" | "error" } | null>(null);

  if (!user) return null;

  const amount = PLANS[user.role];
  const status = user.subscription_status;
  const trialLeft = daysUntil(user.trial_ends_at);

  const subscribe = async () => {
    setLoading(true);
    try {
      // NOTE: Razorpay payment flow is not wired yet (needs API keys).
      // For now we activate locally for demo.
      await api.post<User>("/subscription/activate", { plan: user.role });
      await refresh();
      setToast({ msg: t("success"), variant: "success" });
      setTimeout(() => router.back(), 700);
    } catch (e: any) {
      setToast({ msg: e?.message || "Failed", variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  const features = user.role === "iron_man"
    ? [
        "Unlimited clients",
        "Daily entries with all clothes types",
        "Auto monthly bill generation",
        "Client-wise & yearly reports",
        "PDF bill sharing (coming soon)",
      ]
    : [
        "Real-time view of all your clothes",
        "Monthly & yearly spending reports",
        "Auto-link with your local Iron Man",
        "Payment history & receipts",
        "Reminders for unpaid bills",
      ];

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <Toast visible={!!toast} message={toast?.msg || ""} variant={toast?.variant} onHide={() => setToast(null)} />
      <View style={styles.header}>
        <TouchableOpacity testID="back-button" style={styles.iconBtn} onPress={() => router.back()}>
          <Ionicons name="close" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t("subscription")}</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.xl, paddingBottom: 160 }} showsVerticalScrollIndicator={false}>
        <View style={styles.heroCard}>
          <View style={styles.crown}>
            <Ionicons name="star" size={28} color={colors.textInverse} />
          </View>
          <Text style={styles.title}>{t("subscribe_title")}</Text>
          <Text style={styles.subtitle}>{t("subscribe_desc")}</Text>

          {status === "trial" ? (
            <View style={styles.trialBanner}>
              <Ionicons name="time" size={14} color={colors.primary} />
              <Text style={styles.trialText}>{trialLeft} days trial left</Text>
            </View>
          ) : status === "active" ? (
            <View style={styles.activeBanner}>
              <Ionicons name="checkmark-circle" size={14} color={colors.success} />
              <Text style={styles.activeText}>Active until {formatDate(user.subscription_ends_at)}</Text>
            </View>
          ) : (
            <View style={styles.expiredBanner}>
              <Ionicons name="alert-circle" size={14} color={colors.danger} />
              <Text style={styles.expiredText}>{t("subscription_expired")}</Text>
            </View>
          )}
        </View>

        <View style={styles.planCard}>
          <View style={styles.planHeader}>
            <Text style={styles.planTitle}>{user.role === "iron_man" ? t("iron_man") : t("client")} Premium</Text>
            <View style={styles.priceRow}>
              <Text style={styles.priceMain}>₹{amount}</Text>
              <Text style={styles.priceUnit}>/month</Text>
            </View>
          </View>
          <View style={styles.divider} />
          {features.map((f, i) => (
            <View key={i} style={styles.featureRow}>
              <Ionicons name="checkmark-circle" size={18} color={colors.primary} />
              <Text style={styles.featureText}>{f}</Text>
            </View>
          ))}
          <Text style={styles.trialNote}>{t("free_trial_days", { days: 7 })} • Cancel anytime</Text>
        </View>

        <Text style={styles.notice}>
          Note: Payment integration via Razorpay will be enabled once API keys are configured.
          For now, this button simulates activation for 30 days.
        </Text>
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity
          testID="activate-subscription-button"
          style={[styles.payBtn, (loading || status === "active") && styles.btnDisabled]}
          onPress={subscribe}
          disabled={loading || status === "active"}
        >
          {loading ? <ActivityIndicator color={colors.textInverse} /> : (
            <>
              <Ionicons name="flash" size={18} color={colors.textInverse} />
              <Text style={styles.payBtnText}>
                {status === "active" ? "Already active" : t("pay_now", { amount })}
              </Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: "row", alignItems: "center", padding: spacing.lg, borderBottomWidth: 1, borderBottomColor: colors.borderLight, backgroundColor: colors.card },
  iconBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center", borderRadius: radius.md },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: "800", color: colors.text, textAlign: "center" },

  heroCard: { alignItems: "center", padding: spacing.xl },
  crown: {
    width: 64, height: 64, borderRadius: 32,
    backgroundColor: colors.primary, alignItems: "center", justifyContent: "center",
    marginBottom: spacing.lg,
    shadowColor: colors.primary, shadowOpacity: 0.3, shadowRadius: 16, shadowOffset: { width: 0, height: 8 },
    elevation: 8,
  },
  title: { fontSize: 24, fontWeight: "800", color: colors.text, textAlign: "center" },
  subtitle: { fontSize: 14, color: colors.textSecondary, textAlign: "center", marginTop: 4 },

  trialBanner: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.md, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: "#EEF2FF", borderRadius: radius.pill },
  trialText: { color: colors.primary, fontWeight: "700", fontSize: 12 },
  activeBanner: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.md, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: colors.successLight, borderRadius: radius.pill },
  activeText: { color: colors.success, fontWeight: "700", fontSize: 12 },
  expiredBanner: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.md, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: colors.dangerLight, borderRadius: radius.pill },
  expiredText: { color: colors.danger, fontWeight: "700", fontSize: 12 },

  planCard: {
    backgroundColor: colors.card, borderRadius: radius.xl, padding: spacing.xl,
    borderWidth: 1, borderColor: colors.border, marginTop: spacing.lg,
    shadowColor: colors.shadow, shadowOpacity: 1, shadowRadius: 12, shadowOffset: { width: 0, height: 4 },
  },
  planHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  planTitle: { fontSize: 18, fontWeight: "800", color: colors.text },
  priceRow: { flexDirection: "row", alignItems: "baseline" },
  priceMain: { fontSize: 32, fontWeight: "800", color: colors.primary },
  priceUnit: { fontSize: 13, color: colors.textSecondary, marginLeft: 2 },
  divider: { height: 1, backgroundColor: colors.borderLight, marginVertical: spacing.lg },
  featureRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: spacing.md },
  featureText: { fontSize: 14, color: colors.text, flex: 1 },
  trialNote: { fontSize: 12, color: colors.textMuted, textAlign: "center", marginTop: spacing.md, fontStyle: "italic" },

  notice: { fontSize: 11, color: colors.textMuted, textAlign: "center", marginTop: spacing.xl, paddingHorizontal: spacing.lg, fontStyle: "italic" },

  footer: {
    position: "absolute", bottom: 0, left: 0, right: 0,
    padding: spacing.lg, backgroundColor: colors.card,
    borderTopWidth: 1, borderTopColor: colors.borderLight,
  },
  payBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
    backgroundColor: colors.primary, height: 52, borderRadius: radius.lg,
    shadowColor: colors.primary, shadowOpacity: 0.3, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 6,
  },
  payBtnText: { color: colors.textInverse, fontSize: 16, fontWeight: "800" },
  btnDisabled: { opacity: 0.6 },
});
