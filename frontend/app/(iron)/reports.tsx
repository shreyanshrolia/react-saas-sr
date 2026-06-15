import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type ClientReportRow, type MonthlyReport } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatINR, formatMonth } from "@/src/utils/format";

type Tab = "monthly" | "yearly" | "client";

export default function ReportsScreen() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("monthly");
  const [monthly, setMonthly] = useState<MonthlyReport[]>([]);
  const [yearly, setYearly] = useState<{ year: string; total_quantity: number; total_amount: number; entries_count: number }[]>([]);
  const [byClient, setByClient] = useState<ClientReportRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, y, b] = await Promise.all([
        api.get<MonthlyReport[]>("/reports/monthly"),
        api.get<any[]>("/reports/yearly"),
        api.get<ClientReportRow[]>("/reports/by-client"),
      ]);
      setMonthly(m);
      setYearly(y);
      setByClient(b);
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
        <Tab2 active={tab === "monthly"} onPress={() => setTab("monthly")} label={t("monthly_report")} testID="report-tab-monthly" />
        <Tab2 active={tab === "yearly"} onPress={() => setTab("yearly")} label={t("yearly_report")} testID="report-tab-yearly" />
        <Tab2 active={tab === "client"} onPress={() => setTab("client")} label={t("client_wise")} testID="report-tab-client" />
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : tab === "monthly" ? (
        <FlatList
          data={monthly}
          keyExtractor={(it) => it.month}
          contentContainerStyle={styles.list}
          ListEmptyComponent={<EmptyView text="No data yet" />}
          renderItem={({ item }) => (
            <View style={styles.reportCard} testID={`monthly-row-${item.month}`}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
                <Text style={styles.cardTitle}>{formatMonth(item.month)}</Text>
                <Text style={styles.cardTotal}>{formatINR(item.total_amount)}</Text>
              </View>
              <View style={styles.statsGrid}>
                <Stat label={t("total_pieces")} value={String(item.total_quantity)} />
                <Stat label="Entries" value={String(item.entries_count)} />
                <Stat label={t("paid_amount")} value={formatINR(item.paid_amount)} color={colors.success} />
                <Stat label={t("unpaid_amount")} value={formatINR(item.unpaid_amount)} color={colors.warning} />
              </View>
            </View>
          )}
        />
      ) : tab === "yearly" ? (
        <FlatList
          data={yearly}
          keyExtractor={(it) => it.year}
          contentContainerStyle={styles.list}
          ListEmptyComponent={<EmptyView text="No data yet" />}
          renderItem={({ item }) => (
            <View style={styles.reportCard} testID={`yearly-row-${item.year}`}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
                <Text style={styles.cardTitle}>{item.year}</Text>
                <Text style={styles.cardTotal}>{formatINR(item.total_amount)}</Text>
              </View>
              <View style={styles.statsGrid}>
                <Stat label={t("total_pieces")} value={String(item.total_quantity)} />
                <Stat label="Entries" value={String(item.entries_count)} />
              </View>
            </View>
          )}
        />
      ) : (
        <ScrollView contentContainerStyle={styles.list}>
          {byClient.length === 0 ? <EmptyView text="No data yet" /> : null}
          {byClient.map((c) => (
            <View key={c.client_id} style={styles.reportCard} testID={`client-row-${c.client_id}`}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
                <View>
                  <Text style={styles.cardTitle}>{c.client_name}</Text>
                  <Text style={styles.cardSub}>+91 {c.client_phone}</Text>
                </View>
                <Text style={styles.cardTotal}>{formatINR(c.total_amount)}</Text>
              </View>
              <View style={styles.statsGrid}>
                <Stat label={t("total_pieces")} value={String(c.total_quantity)} />
                <Stat label={t("paid_amount")} value={formatINR(c.paid_amount)} color={colors.success} />
                <Stat label={t("unpaid_amount")} value={formatINR(c.unpaid_amount)} color={colors.warning} />
              </View>
            </View>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

function Tab2({ active, label, onPress, testID }: { active: boolean; label: string; onPress: () => void; testID?: string }) {
  return (
    <TouchableOpacity testID={testID} style={[styles.tabBtn, active && styles.tabBtnActive]} onPress={onPress} activeOpacity={0.8}>
      <Text style={[styles.tabText, active && styles.tabTextActive]}>{label}</Text>
    </TouchableOpacity>
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

function EmptyView({ text }: { text: string }) {
  return (
    <View style={{ alignItems: "center", padding: spacing.xxxl, gap: spacing.md }}>
      <Ionicons name="bar-chart-outline" size={48} color={colors.textMuted} />
      <Text style={{ color: colors.textSecondary }}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { padding: spacing.xl, paddingBottom: spacing.md },
  title: { fontSize: 26, fontWeight: "800", color: colors.text },

  tabsRow: { flexDirection: "row", gap: 8, paddingHorizontal: spacing.xl, marginBottom: spacing.md },
  tabBtn: {
    flex: 1, paddingVertical: 10, borderRadius: radius.md,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, alignItems: "center",
  },
  tabBtnActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  tabText: { fontSize: 12, fontWeight: "700", color: colors.textSecondary },
  tabTextActive: { color: colors.textInverse },

  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  list: { padding: spacing.lg, paddingBottom: 100 },

  reportCard: {
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.md,
  },
  cardTitle: { fontSize: 16, fontWeight: "700", color: colors.text },
  cardSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  cardTotal: { fontSize: 18, fontWeight: "800", color: colors.primary },

  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  stat: { flexBasis: "47%", padding: spacing.md, backgroundColor: colors.bgSecondary, borderRadius: radius.md },
  statLabel: { fontSize: 11, color: colors.textMuted, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5 },
  statValue: { fontSize: 14, fontWeight: "700", color: colors.text, marginTop: 4 },
});
