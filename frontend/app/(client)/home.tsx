import { useCallback, useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Bill, type Entry, type IronManLink } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { currentMonthKey, formatDate, formatINR } from "@/src/utils/format";

export default function ClientHome() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [ironMen, setIronMen] = useState<IronManLink[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [im, en, bi] = await Promise.all([
        api.get<IronManLink[]>("/my/iron-men"),
        api.get<Entry[]>("/entries?status_filter=pending"),
        api.get<Bill[]>("/bills"),
      ]);
      setIronMen(im);
      setEntries(en);
      setBills(bi);
    } catch {
      // ignore
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const cm = currentMonthKey();
  const monthAmount = bills
    .filter((b) => b.month === cm)
    .reduce((s, b) => s + b.total_amount, 0);
  const unpaidAmount = bills
    .filter((b) => !b.paid)
    .reduce((s, b) => s + b.total_amount, 0);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: 100 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.primary} />}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>{t("welcome_back")},</Text>
            <Text style={styles.name}>{user?.name}</Text>
          </View>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{user?.name.charAt(0).toUpperCase()}</Text>
          </View>
        </View>

        {loading ? (
          <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
        ) : (
          <>
            <View style={styles.heroCard} testID="client-month-card">
              <Text style={styles.heroLabel}>{t("this_month")}</Text>
              <Text style={styles.heroAmount}>{formatINR(monthAmount)}</Text>
              <View style={styles.heroRow}>
                <View style={styles.heroPill}>
                  <Ionicons name="time-outline" size={14} color={colors.textInverse} />
                  <Text style={styles.heroPillText}>{entries.length} {t("pending")}</Text>
                </View>
                {unpaidAmount > 0 ? (
                  <View style={styles.heroPill}>
                    <Ionicons name="alert-circle-outline" size={14} color={colors.textInverse} />
                    <Text style={styles.heroPillText}>{formatINR(unpaidAmount)} {t("unpaid")}</Text>
                  </View>
                ) : null}
              </View>
            </View>

            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{t("your_dhobi")}</Text>
              {ironMen.length === 0 ? (
                <View style={styles.emptyCard}>
                  <Ionicons name="hammer-outline" size={32} color={colors.textMuted} />
                  <Text style={styles.emptyText}>{t("no_dhobi")}</Text>
                  <View style={styles.phoneBox}>
                    <Ionicons name="call" size={14} color={colors.primary} />
                    <Text style={styles.phoneBoxText}>Share: +91 {user?.phone}</Text>
                  </View>
                </View>
              ) : (
                ironMen.map((im) => (
                  <View key={im.iron_man_id} style={styles.imCard} testID={`im-card-${im.iron_man_id}`}>
                    <View style={styles.imAvatar}>
                      <Ionicons name="hammer" size={20} color={colors.primary} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.imName}>{im.iron_man_name}</Text>
                      <Text style={styles.imPhone}>+91 {im.iron_man_phone}</Text>
                    </View>
                    <View style={{ alignItems: "flex-end" }}>
                      <Text style={styles.rateLabel}>Rate</Text>
                      <Text style={styles.rateVal}>{formatINR(im.default_rate)}</Text>
                    </View>
                  </View>
                ))
              )}
            </View>

            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{t("your_clothes")} ({t("pending")})</Text>
              {entries.length === 0 ? (
                <View style={styles.emptyCard}>
                  <Ionicons name="shirt-outline" size={32} color={colors.textMuted} />
                  <Text style={styles.emptyText}>No pending clothes</Text>
                </View>
              ) : (
                entries.slice(0, 5).map((e) => (
                  <View key={e.id} style={styles.entryCard} testID={`entry-${e.id}`}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.entryDate}>{formatDate(e.date_given)}</Text>
                      <Text style={styles.entrySub}>{e.total_quantity} {t("pieces")} • {e.items.length} {t("items")}</Text>
                    </View>
                    <Text style={styles.entryAmount}>{formatINR(e.total_amount)}</Text>
                  </View>
                ))
              )}
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: spacing.xl, paddingBottom: spacing.md },
  greeting: { fontSize: 13, color: colors.textSecondary },
  name: { fontSize: 24, fontWeight: "800", color: colors.text, marginTop: 2 },
  avatar: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  avatarText: { fontSize: 18, fontWeight: "700", color: colors.textInverse },

  center: { padding: spacing.xxxl, alignItems: "center" },
  heroCard: {
    margin: spacing.lg, padding: spacing.xl, borderRadius: radius.xl,
    backgroundColor: colors.primary,
    shadowColor: colors.primary, shadowOpacity: 0.25, shadowRadius: 16, shadowOffset: { width: 0, height: 8 }, elevation: 8,
  },
  heroLabel: { color: "rgba(255,255,255,0.7)", fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 1 },
  heroAmount: { color: colors.textInverse, fontSize: 38, fontWeight: "800", marginTop: 4 },
  heroRow: { flexDirection: "row", gap: 8, marginTop: spacing.md, flexWrap: "wrap" },
  heroPill: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill, backgroundColor: "rgba(255,255,255,0.18)" },
  heroPillText: { color: colors.textInverse, fontSize: 11, fontWeight: "700" },

  section: { paddingHorizontal: spacing.lg, marginTop: spacing.lg },
  sectionTitle: { fontSize: 12, fontWeight: "700", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: spacing.md },

  emptyCard: { alignItems: "center", padding: spacing.xl, backgroundColor: colors.card, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.borderLight, gap: spacing.sm },
  emptyText: { fontSize: 13, color: colors.textSecondary, textAlign: "center" },
  phoneBox: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: "#EEF2FF", paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, marginTop: 4 },
  phoneBoxText: { color: colors.primary, fontWeight: "700", fontSize: 12 },

  imCard: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.sm,
  },
  imAvatar: { width: 40, height: 40, borderRadius: radius.md, backgroundColor: "#EEF2FF", alignItems: "center", justifyContent: "center", marginRight: spacing.md },
  imName: { fontSize: 15, fontWeight: "700", color: colors.text },
  imPhone: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  rateLabel: { fontSize: 10, color: colors.textMuted, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5 },
  rateVal: { fontSize: 14, fontWeight: "700", color: colors.text, marginTop: 2 },

  entryCard: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.sm,
  },
  entryDate: { fontSize: 14, fontWeight: "700", color: colors.text },
  entrySub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  entryAmount: { fontSize: 16, fontWeight: "800", color: colors.primary },
});
