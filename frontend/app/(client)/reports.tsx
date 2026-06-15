import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type MonthlyReport } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatINR, formatMonth } from "@/src/utils/format";

export default function ClientReports() {
  const { t } = useI18n();
  const [tab, setTab] = useState<"monthly" | "yearly">("monthly");
  const [monthly, setMonthly] = useState<MonthlyReport[]>([]);
  const [yearly, setYearly] = useState<{ year: string; total_quantity: number; total_amount: number; entries_count: number }[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, y] = await Promise.all([
        api.get<MonthlyReport[]>("/reports/monthly"),
        api.get<any[]>("/reports/yearly"),
      ]);
      setMonthly(m);
      setYearly(y);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.title}>{t("tab_reports")}</Text>
      </View>

      <View style={styles.tabsRow}>
        <TouchableOpacity testID="c-report-monthly" style={[styles.tabBtn, tab === "monthly" && styles.tabBtnActive]} onPress={() => setTab("monthly")}>
          <Text style={[styles.tabText, tab === "monthly" && styles.tabTextActive]}>{t("monthly_report")}</Text>
        </TouchableOpacity>
        <TouchableOpacity testID="c-report-yearly" style={[styles.tabBtn, tab === "yearly" && styles.tabBtnActive]} onPress={() => setTab("yearly")}>
          <Text style={[styles.tabText, tab === "yearly" && styles.tabTextActive]}>{t("yearly_report")}</Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : tab === "monthly" ? (
        <FlatList
          data={monthly}
          keyExtractor={(it) => it.month}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
          ListEmptyComponent={<Empty />}
          renderItem={({ item }) => (
            <View style={styles.card} testID={`c-monthly-${item.month}`}>
              <View style={styles.rowBetween}>
                <Text style={styles.cardTitle}>{formatMonth(item.month)}</Text>
                <Text style={styles.cardTotal}>{formatINR(item.total_amount)}</Text>
              </View>
              <View style={styles.grid}>
                <Stat label={t("total_pieces")} value={String(item.total_quantity)} />
                <Stat label="Entries" value={String(item.entries_count)} />
                <Stat label={t("paid_amount")} value={formatINR(item.paid_amount)} color={colors.success} />
                <Stat label={t("unpaid_amount")} value={formatINR(item.unpaid_amount)} color={colors.warning} />
              </View>
            </View>
          )}
        />
      ) : (
        <FlatList
          data={yearly}
          keyExtractor={(it) => it.year}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
          ListEmptyComponent={<Empty />}
          renderItem={({ item }) => (
            <View style={styles.card} testID={`c-yearly-${item.year}`}>
              <View style={styles.rowBetween}>
                <Text style={styles.cardTitle}>{item.year}</Text>
                <Text style={styles.cardTotal}>{formatINR(item.total_amount)}</Text>
              </View>
              <View style={styles.grid}>
                <Stat label={t("total_pieces")} value={String(item.total_quantity)} />
                <Stat label="Entries" value={String(item.entries_count)} />
              </View>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
    </View>
  );
}

function Empty() {
  return (
    <View style={{ alignItems: "center", padding: spacing.xxxl, gap: spacing.md }}>
      <Ionicons name="bar-chart-outline" size={48} color={colors.textMuted} />
      <Text style={{ color: colors.textSecondary }}>No data yet</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { padding: spacing.xl, paddingBottom: spacing.md },
  title: { fontSize: 26, fontWeight: "800", color: colors.text },
  tabsRow: { flexDirection: "row", gap: 8, paddingHorizontal: spacing.xl, marginBottom: spacing.md },
  tabBtn: { flex: 1, paddingVertical: 10, borderRadius: radius.md, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  tabBtnActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  tabText: { fontSize: 12, fontWeight: "700", color: colors.textSecondary },
  tabTextActive: { color: colors.textInverse },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.md },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md },
  cardTitle: { fontSize: 16, fontWeight: "700", color: colors.text },
  cardTotal: { fontSize: 18, fontWeight: "800", color: colors.primary },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  stat: { flexBasis: "47%", padding: spacing.md, backgroundColor: colors.bgSecondary, borderRadius: radius.md },
  statLabel: { fontSize: 11, color: colors.textMuted, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5 },
  statValue: { fontSize: 14, fontWeight: "700", color: colors.text, marginTop: 4 },
});
