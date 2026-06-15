import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Bill } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatINR, formatMonth } from "@/src/utils/format";

const STATUS_COLORS: Record<Bill["status"], { bg: string; fg: string; label: string }> = {
  paid: { bg: colors.successLight, fg: colors.success, label: "Paid" },
  overpaid: { bg: "#DBEAFE", fg: colors.primary, label: "Overpaid" },
  partial: { bg: "#FEF3C7", fg: "#B45309", label: "Partial" },
  unpaid: { bg: colors.warningLight, fg: colors.warning, label: "Unpaid" },
};

export default function ClientBills() {
  const { t } = useI18n();
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<"all" | "paid" | "unpaid">("all");

  const load = useCallback(async () => {
    try {
      const data = await api.get<Bill[]>("/bills");
      setBills(data);
    } catch {/* ignore */} finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const filtered = bills.filter((b) => {
    if (filter === "all") return true;
    if (filter === "paid") return b.status === "paid" || b.status === "overpaid";
    return b.status === "unpaid" || b.status === "partial";
  });

  const totalUnpaid = bills
    .filter((b) => b.status === "unpaid" || b.status === "partial")
    .reduce((s, b) => s + b.balance, 0);
  const totalPaid = bills.reduce((s, b) => s + b.amount_paid, 0);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.title}>{t("your_bills")}</Text>
      </View>

      <View style={styles.statsRow}>
        <View style={[styles.statCard, { backgroundColor: colors.warningLight }]}>
          <Text style={[styles.statValue, { color: colors.warning }]}>{formatINR(totalUnpaid)}</Text>
          <Text style={[styles.statLabel, { color: colors.warning }]}>You owe</Text>
        </View>
        <View style={[styles.statCard, { backgroundColor: colors.successLight }]}>
          <Text style={[styles.statValue, { color: colors.success }]}>{formatINR(totalPaid)}</Text>
          <Text style={[styles.statLabel, { color: colors.success }]}>{t("paid")}</Text>
        </View>
      </View>

      <View style={styles.chipsRow}>
        <Chip testID="c-filter-all" label="All" active={filter === "all"} onPress={() => setFilter("all")} />
        <Chip testID="c-filter-unpaid" label={t("unpaid")} active={filter === "unpaid"} onPress={() => setFilter("unpaid")} />
        <Chip testID="c-filter-paid" label={t("paid")} active={filter === "paid"} onPress={() => setFilter("paid")} />
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
          keyExtractor={(it) => it.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.primary} />}
          renderItem={({ item }) => <BillRow bill={item} t={t} />}
        />
      )}
    </SafeAreaView>
  );
}

function BillRow({ bill, t }: { bill: Bill; t: (k: any) => string }) {
  const sc = STATUS_COLORS[bill.status];
  return (
    <View style={styles.billCard} testID={`bill-${bill.id}`}>
      <View style={styles.billHeader}>
        <View style={{ flex: 1 }}>
          <Text style={styles.billMonth}>{formatMonth(bill.month)}</Text>
          <Text style={styles.billSub}>{bill.total_quantity} {t("pieces")} • {bill.client_name}</Text>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: sc.bg }]}>
          <Text style={[styles.statusText, { color: sc.fg }]}>{sc.label}</Text>
        </View>
      </View>

      <View style={styles.breakdown}>
        <Row label={t("clothes_amount")} value={formatINR(bill.clothes_amount)} />
        {bill.carry_in !== 0 ? (
          <Row
            label={t("carry_forward")}
            value={`${bill.carry_in > 0 ? "+" : ""}${formatINR(bill.carry_in)}`}
            color={bill.carry_in > 0 ? colors.warning : colors.success}
          />
        ) : null}
        <Row label={t("net_due")} value={formatINR(bill.net_due)} bold />
        <Row label={t("amount_paid")} value={`− ${formatINR(bill.amount_paid)}`} color={colors.success} />
        <View style={styles.divider} />
        <Row
          label={bill.balance < 0 ? "Credit balance" : t("balance")}
          value={formatINR(Math.abs(bill.balance))}
          color={bill.balance > 0 ? colors.warning : bill.balance < 0 ? colors.primary : colors.success}
          big
        />
      </View>
    </View>
  );
}

function Row({ label, value, color, bold, big }: { label: string; value: string; color?: string; bold?: boolean; big?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={[styles.rowLabel, big && { fontSize: 13 }]}>{label}</Text>
      <Text style={[
        styles.rowValue,
        bold && { fontWeight: "800" },
        big && { fontSize: 18, fontWeight: "800" },
        color ? { color } : null,
      ]}>{value}</Text>
    </View>
  );
}

function Chip({ label, active, onPress, testID }: { label: string; active: boolean; onPress: () => void; testID?: string }) {
  return (
    <TouchableOpacity testID={testID} style={[styles.chip, active && styles.chipActive]} onPress={onPress}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { padding: spacing.xl, paddingBottom: spacing.md },
  title: { fontSize: 26, fontWeight: "800", color: colors.text },

  statsRow: { flexDirection: "row", gap: spacing.md, paddingHorizontal: spacing.xl, marginBottom: spacing.md },
  statCard: { flex: 1, padding: spacing.lg, borderRadius: radius.lg },
  statValue: { fontSize: 20, fontWeight: "800" },
  statLabel: { fontSize: 11, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 2 },

  chipsRow: { flexDirection: "row", gap: 8, paddingHorizontal: spacing.xl, marginBottom: spacing.md },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 12, color: colors.textSecondary, fontWeight: "600" },
  chipTextActive: { color: colors.textInverse },

  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  emptyText: { color: colors.textSecondary },

  billCard: { backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.md },
  billHeader: { flexDirection: "row", alignItems: "center" },
  billMonth: { fontSize: 16, fontWeight: "700", color: colors.text },
  billSub: { fontSize: 12, color: colors.textSecondary, marginTop: 4 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  statusText: { fontSize: 10, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.5 },

  breakdown: { marginTop: spacing.md, padding: spacing.md, backgroundColor: colors.bgSecondary, borderRadius: radius.md, gap: 6 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  rowLabel: { fontSize: 12, color: colors.textSecondary, fontWeight: "600" },
  rowValue: { fontSize: 13, color: colors.text, fontWeight: "600" },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 4 },
});
