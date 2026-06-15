import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Bill } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatINR, formatMonth } from "@/src/utils/format";

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
    } catch {
      // ignore
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const filtered = bills.filter((b) => filter === "all" ? true : filter === "paid" ? b.paid : !b.paid);
  const totalUnpaid = bills.filter((b) => !b.paid).reduce((s, b) => s + b.total_amount, 0);
  const totalPaid = bills.filter((b) => b.paid).reduce((s, b) => s + b.total_amount, 0);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.title}>{t("your_bills")}</Text>
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
          renderItem={({ item }) => (
            <View style={styles.billCard} testID={`bill-${item.id}`}>
              <View style={{ flex: 1 }}>
                <Text style={styles.billMonth}>{formatMonth(item.month)}</Text>
                <Text style={styles.billSub}>{item.total_quantity} {t("pieces")} • {item.client_name}</Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={styles.billAmount}>{formatINR(item.total_amount)}</Text>
                <View style={[styles.statusBadge, item.paid ? styles.paidBadge : styles.unpaidBadge]}>
                  <Ionicons name={item.paid ? "checkmark-circle" : "time"} size={12} color={item.paid ? colors.success : colors.warning} />
                  <Text style={[styles.statusText, { color: item.paid ? colors.success : colors.warning }]}>
                    {item.paid ? t("paid") : t("unpaid")}
                  </Text>
                </View>
              </View>
            </View>
          )}
        />
      )}
    </SafeAreaView>
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

  billCard: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.md,
  },
  billMonth: { fontSize: 16, fontWeight: "700", color: colors.text },
  billSub: { fontSize: 12, color: colors.textSecondary, marginTop: 4 },
  billAmount: { fontSize: 18, fontWeight: "800", color: colors.text, marginBottom: 6 },

  statusBadge: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  paidBadge: { backgroundColor: colors.successLight },
  unpaidBadge: { backgroundColor: colors.warningLight },
  statusText: { fontSize: 11, fontWeight: "700" },
});
