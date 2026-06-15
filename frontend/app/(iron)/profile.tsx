import { useState } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/src/contexts/AuthContext";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { daysUntil, formatDate } from "@/src/utils/format";

export default function ProfileScreen() {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const router = useRouter();
  const [confirmLogout, setConfirmLogout] = useState(false);

  if (!user) return null;

  const status = user.subscription_status;
  const trialDays = daysUntil(user.trial_ends_at);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={{ padding: spacing.xl, paddingBottom: 100 }}>
        <View style={styles.profileCard}>
          <View style={styles.avatarBig}>
            <Text style={styles.avatarBigText}>{user.name.charAt(0).toUpperCase()}</Text>
          </View>
          <Text style={styles.name}>{user.name}</Text>
          <View style={styles.roleBadge}>
            <Ionicons
              name={user.role === "iron_man" ? "hammer" : "home"}
              size={12}
              color={colors.primary}
            />
            <Text style={styles.roleBadgeText}>{user.role === "iron_man" ? t("iron_man") : t("client")}</Text>
          </View>
          <Text style={styles.phone}>+91 {user.phone}</Text>
          {user.address ? <Text style={styles.addr}>{user.address}</Text> : null}
        </View>

        <View style={[styles.section, styles.subSection]}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Text style={styles.sectionTitle}>{t("subscription")}</Text>
            <View style={[styles.subBadge, status === "active" ? styles.subActive : status === "trial" ? styles.subTrial : styles.subExpired]}>
              <Text style={[styles.subBadgeText, { color: status === "active" ? colors.success : status === "trial" ? colors.primary : colors.danger }]}>
                {status === "active" ? "ACTIVE" : status === "trial" ? "TRIAL" : "EXPIRED"}
              </Text>
            </View>
          </View>
          {status === "trial" ? (
            <>
              <Text style={styles.subText}>{t("trial_active")}</Text>
              <Text style={styles.subDates}>
                {trialDays} days left • {t("trial_ends")} {formatDate(user.trial_ends_at)}
              </Text>
            </>
          ) : status === "active" ? (
            <>
              <Text style={styles.subText}>{t("subscription_active")}</Text>
              <Text style={styles.subDates}>{formatDate(user.subscription_ends_at)}</Text>
            </>
          ) : (
            <Text style={styles.subText}>{t("subscription_expired")}</Text>
          )}
          <TouchableOpacity
            testID="open-subscription-button"
            style={styles.upgradeBtn}
            onPress={() => router.push("/subscription")}
          >
            <Ionicons name="star" size={16} color={colors.textInverse} />
            <Text style={styles.upgradeBtnText}>{status === "active" ? t("subscription") : t("upgrade")}</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{t("language")}</Text>
          <View style={styles.langRow}>
            <TouchableOpacity
              testID="lang-en"
              style={[styles.langChip, lang === "en" && styles.langChipActive]}
              onPress={() => setLang("en")}
            >
              <Text style={[styles.langChipText, lang === "en" && styles.langChipTextActive]}>{t("english")}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="lang-hi"
              style={[styles.langChip, lang === "hi" && styles.langChipActive]}
              onPress={() => setLang("hi")}
            >
              <Text style={[styles.langChipText, lang === "hi" && styles.langChipTextActive]}>{t("hindi")}</Text>
            </TouchableOpacity>
          </View>
        </View>

        {confirmLogout ? (
          <View style={styles.confirmBox}>
            <Text style={styles.confirmText}>{t("confirm")}?</Text>
            <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.md }}>
              <TouchableOpacity testID="cancel-logout" style={styles.cancelBtn} onPress={() => setConfirmLogout(false)}>
                <Text style={styles.cancelBtnText}>{t("cancel")}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                testID="confirm-logout"
                style={styles.logoutBtnDanger}
                onPress={async () => { await logout(); router.replace("/(auth)/login"); }}
              >
                <Text style={styles.logoutBtnDangerText}>{t("logout")}</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <TouchableOpacity testID="logout-button" style={styles.logoutBtn} onPress={() => setConfirmLogout(true)}>
            <Ionicons name="log-out-outline" size={18} color={colors.danger} />
            <Text style={styles.logoutBtnText}>{t("logout")}</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  profileCard: {
    alignItems: "center",
    padding: spacing.xl,
    backgroundColor: colors.card,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  avatarBig: {
    width: 80, height: 80, borderRadius: 40, backgroundColor: colors.primary,
    alignItems: "center", justifyContent: "center", marginBottom: spacing.md,
  },
  avatarBigText: { fontSize: 32, fontWeight: "800", color: colors.textInverse },
  name: { fontSize: 20, fontWeight: "800", color: colors.text },
  roleBadge: {
    flexDirection: "row", alignItems: "center", gap: 4,
    marginTop: 8, backgroundColor: "#EEF2FF",
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill,
  },
  roleBadgeText: { fontSize: 11, color: colors.primary, fontWeight: "700" },
  phone: { fontSize: 14, color: colors.textSecondary, marginTop: 8 },
  addr: { fontSize: 12, color: colors.textMuted, marginTop: 4, textAlign: "center" },

  section: { marginTop: spacing.xl, padding: spacing.lg, backgroundColor: colors.card, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.borderLight },
  subSection: {},
  sectionTitle: { fontSize: 12, fontWeight: "700", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5 },

  subBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  subActive: { backgroundColor: colors.successLight },
  subTrial: { backgroundColor: "#EEF2FF" },
  subExpired: { backgroundColor: colors.dangerLight },
  subBadgeText: { fontSize: 10, fontWeight: "800" },

  subText: { fontSize: 15, fontWeight: "700", color: colors.text, marginTop: spacing.md },
  subDates: { fontSize: 12, color: colors.textSecondary, marginTop: 4 },

  upgradeBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: colors.primary, paddingVertical: 12, borderRadius: radius.md,
    justifyContent: "center", marginTop: spacing.md,
  },
  upgradeBtnText: { color: colors.textInverse, fontWeight: "700" },

  langRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  langChip: {
    flex: 1, paddingVertical: 10, borderRadius: radius.md,
    backgroundColor: colors.bgSecondary, alignItems: "center",
    borderWidth: 1, borderColor: colors.border,
  },
  langChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  langChipText: { fontWeight: "700", color: colors.textSecondary },
  langChipTextActive: { color: colors.textInverse },

  logoutBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
    marginTop: spacing.xl, padding: spacing.md, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.dangerLight,
  },
  logoutBtnText: { color: colors.danger, fontWeight: "700" },

  confirmBox: { marginTop: spacing.xl, padding: spacing.lg, backgroundColor: colors.dangerLight, borderRadius: radius.lg },
  confirmText: { color: colors.danger, fontWeight: "700", textAlign: "center" },
  cancelBtn: { flex: 1, padding: 12, borderRadius: radius.md, backgroundColor: colors.card, alignItems: "center" },
  cancelBtnText: { color: colors.text, fontWeight: "700" },
  logoutBtnDanger: { flex: 1, padding: 12, borderRadius: radius.md, backgroundColor: colors.danger, alignItems: "center" },
  logoutBtnDangerText: { color: colors.textInverse, fontWeight: "700" },
});
