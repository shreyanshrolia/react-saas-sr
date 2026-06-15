import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Bill } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { currentMonthKey, formatINR, formatMonth } from "@/src/utils/format";
import Toast from "@/src/components/Toast";

export default function BillsScreen() {
  const { t } = useI18n();
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [filter, setFilter] = useState<"all" | "paid" | "unpaid">("all");
  const [monthFilter, setMonthFilter] = useState<string>("all");
  const [toast, setToast] = useState<{ msg: string; variant?: "success" | "error" } | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get<Bill[]>("/bills");
      setBills(data);
    } catch (e: any) {
      setToast({ msg: e?.message || "Failed", variant: "error" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const generate = async () => {
    setGenerating(true);
    try {
      await api.post("/bills/generate");
      setToast({ msg: "Bills updated", variant: "success" });
      await load();
    } catch (e: any) {
      setToast({ msg: e?.message || "Failed", variant: "error" });
    } finally {
      setGenerating(false);
    }
  };

  const toggle = async (b: Bill) => {
    try {
      const updated = await api.post<Bill>(`/bills/${b.id}/paid`, { paid: !b.paid });
      setBills((cur) => cur.map((x) => (x.id === b.id ? updated : x)));
      setToast({ msg: updated.paid ? t("paid") : t("unpaid"), variant: "success" });
    } catch (e: any) {
      setToast({ msg: e?.message || "Failed", variant: "error" });
    }
  };

  const months = Array.from(new Set(bills.map((b) => b.month))).sort().reverse();
  const filteredByMonth = monthFilter === "all" ? bills : bills.filter((b) => b.month === monthFilter);
  const filtered = filteredByMonth.filter((b) => {
    if (filter === "paid") return b.paid;
    if (filter === "unpaid") return !b.paid;
    return true;
  });

  const totalUnpaid = filtered.filter((b) => !b.paid).reduce((s, b) => s + b.total_amount, 0);
  const totalPaid = filtered.filter((b) => b.paid).reduce((s, b) => s + b.total_amount, 0);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast visible={!!toast} message={toast?.msg || ""} variant={toast?.variant} onHide={() => setToast(null)} />
      <View style={styles.header}>
        <Text style={styles.title}>{t("bills_title")}</Text>
        <TouchableOpacity
          testID="generate-bills-button"
          style={styles.genBtn}
          onPress={generate}
          disabled={generating}
        >
          {generating ? (
            <ActivityIndicator size="small" color={colors.primary} />
          ) : (
            <>
              <Ionicons name="refresh" size={16} color={colors.primary} />
              <Text style={styles.genBtnText}>{t("generate_bills")}</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.statsRow}>
        <View style={[styles.statCard, { backgroundColor: colors.warningLight }]}>
          <Text style={[styles.statValue, { color: colors.warning }]}>{formatINR(totalUnpaid)}</Text>
          <Text style={[styles.statLabel, { color: colors.warning }]}>{t("unpaid")}</Text>
        </View>
        <View style={[styles.statCard, { backgroundColor: colors.successLight }]}>
          <Text style={[styles.statValue, { color: colors.success }]}>{formatINR(totalPaid)}</Text>
          <Text style={[styles.statLabel, { color: colors.success }]}>{t("paid")}</Text>
        </View>
      </View>

      <View style={styles.filtersWrap}>
        <FilterChip label="All" active={filter === "all"} onPress={() => setFilter("all")} testID="filter-all" />
        <FilterChip label={t("unpaid")} active={filter === "unpaid"} onPress={() => setFilter("unpaid")} testID="filter-unpaid" />
        <FilterChip label={t("paid")} active={filter === "paid"} onPress={() => setFilter("paid")} testID="filter-paid" />
        <View style={{ width: 1, backgroundColor: colors.border, marginHorizontal: 4 }} />
        <FilterChip label={t("month")} active={monthFilter !== "all"} onPress={() => setMonthFilter(monthFilter === "all" ? currentMonthKey() : "all")} testID="filter-month-toggle" />
        {monthFilter !== "all" ? <Text style={styles.monthLabel}>{formatMonth(monthFilter)}</Text> : null}
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : filtered.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="receipt-outline" size={56} color={colors.textMuted} />
          <Text style={styles.emptyText}>{t("no_bills")}</Text>
        </View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(b) => b.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.primary} />}
          renderItem={({ item }) => (
            <View style={styles.billCard} testID={`bill-card-${item.id}`}>
              <View style={{ flex: 1 }}>
                <Text style={styles.billClient}>{item.client_name}</Text>
                <Text style={styles.billPhone}>+91 {item.client_phone}</Text>
                <Text style={styles.billMonth}>{formatMonth(item.month)} • {item.total_quantity} {t("pieces")}</Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={styles.billAmount}>{formatINR(item.total_amount)}</Text>
                <TouchableOpacity
                  testID={`bill-toggle-${item.id}`}
                  style={[styles.statusBadge, item.paid ? styles.paidBadge : styles.unpaidBadge]}
                  onPress={() => toggle(item)}
                  activeOpacity={0.8}
                >
                  <Ionicons name={item.paid ? "checkmark-circle" : "time"} size={12} color={item.paid ? colors.success : colors.warning} />
                  <Text style={[styles.statusText, { color: item.paid ? colors.success : colors.warning }]}>
                    {item.paid ? t("paid") : t("unpaid")}
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
          ListHeaderComponent={months.length > 1 ? (
            <View style={styles.monthChipsRow}>
              <FilterChip label="All months" active={monthFilter === "all"} onPress={() => setMonthFilter("all")} testID="month-all" />
              {months.map((m) => (
                <FilterChip
                  key={m}
                  label={formatMonth(m)}
                  active={monthFilter === m}
                  onPress={() => setMonthFilter(m)}
                  testID={`month-${m}`}
                />
              ))}
            </View>
          ) : null}
        />
      )}
    </SafeAreaView>
  );
}

function FilterChip({ label, active, onPress, testID }: { label: string; active: boolean; onPress: () => void; testID?: string }) {
  return (
    <TouchableOpacity
      testID={testID}
      style={[styles.chip, active && styles.chipActive]}
      onPress={onPress}
      activeOpacity={0.8}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: spacing.xl, paddingBottom: spacing.md },
  title: { fontSize: 26, fontWeight: "800", color: colors.text },
  genBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: radius.pill,
    backgroundColor: "#EEF2FF", borderWidth: 1, borderColor: colors.primary + "33",
  },
  genBtnText: { color: colors.primary, fontWeight: "700", fontSize: 12 },
  statsRow: { flexDirection: "row", gap: spacing.md, paddingHorizontal: spacing.xl, marginBottom: spacing.md },
  statCard: { flex: 1, padding: spacing.lg, borderRadius: radius.lg },
  statValue: { fontSize: 20, fontWeight: "800" },
  statLabel: { fontSize: 11, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 2 },

  filtersWrap: {
    flexDirection: "row", alignItems: "center", gap: 8,
    paddingHorizontal: spacing.xl, paddingBottom: spacing.md, flexWrap: "wrap",
  },
  monthLabel: { fontSize: 12, color: colors.primary, fontWeight: "700" },

  chip: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 12, color: colors.textSecondary, fontWeight: "600" },
  chipTextActive: { color: colors.textInverse },

  monthChipsRow: { flexDirection: "row", gap: 8, marginBottom: spacing.md, flexWrap: "wrap" },

  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  emptyText: { fontSize: 14, color: colors.textSecondary },

  billCard: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.md,
  },
  billClient: { fontSize: 15, fontWeight: "700", color: colors.text },
  billPhone: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  billMonth: { fontSize: 11, color: colors.textMuted, marginTop: 4 },
  billAmount: { fontSize: 18, fontWeight: "800", color: colors.text, marginBottom: 6 },

  statusBadge: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill,
  },
  paidBadge: { backgroundColor: colors.successLight },
  unpaidBadge: { backgroundColor: colors.warningLight },
  statusText: { fontSize: 11, fontWeight: "700" },
});
