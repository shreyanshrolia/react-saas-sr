import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Client, type Entry } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatDate, formatINR } from "@/src/utils/format";
import Toast from "@/src/components/Toast";

export default function ClientDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { t } = useI18n();
  const [client, setClient] = useState<Client | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "pending" | "returned">("all");
  const [toast, setToast] = useState<{ msg: string; variant?: "success" | "error" } | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [c, e] = await Promise.all([
        api.get<Client>(`/clients/${id}`),
        api.get<Entry[]>(`/entries?client_id=${id}`),
      ]);
      setClient(c);
      setEntries(e);
    } catch (err: any) {
      setToast({ msg: err?.message || "Failed", variant: "error" });
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const markReturned = async (entryId: string) => {
    try {
      const u = await api.post<Entry>(`/entries/${entryId}/return`, {});
      setEntries((cur) => cur.map((e) => (e.id === entryId ? u : e)));
      setToast({ msg: t("returned"), variant: "success" });
    } catch (e: any) {
      setToast({ msg: e?.message || "Failed", variant: "error" });
    }
  };

  const deleteEntry = async (entryId: string) => {
    try {
      await api.delete(`/entries/${entryId}`);
      setEntries((cur) => cur.filter((e) => e.id !== entryId));
      setToast({ msg: "Deleted", variant: "success" });
    } catch (e: any) {
      setToast({ msg: e?.message || "Failed", variant: "error" });
    }
  };

  const filtered = entries.filter((e) => (filter === "all" ? true : e.status === filter));

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}><View style={styles.center}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>
    );
  }
  if (!client) return null;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast visible={!!toast} message={toast?.msg || ""} variant={toast?.variant} onHide={() => setToast(null)} />
      <View style={styles.header}>
        <TouchableOpacity testID="back-button" style={styles.iconBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{client.name}</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 100 }}>
        <View style={styles.profileBlock}>
          <View style={styles.avatarBig}>
            <Text style={styles.avatarBigText}>{client.name.charAt(0).toUpperCase()}</Text>
          </View>
          <Text style={styles.clientName}>{client.name}</Text>
          <Text style={styles.clientPhone}>+91 {client.phone}</Text>
          {client.address ? <Text style={styles.clientAddr}>{client.address}</Text> : null}
          {client.linked_user_id ? (
            <View style={styles.linkedBadge}>
              <Ionicons name="link" size={12} color={colors.success} />
              <Text style={styles.linkedText}>App connected</Text>
            </View>
          ) : (
            <View style={[styles.linkedBadge, { backgroundColor: colors.bgSecondary }]}>
              <Ionicons name="hourglass" size={12} color={colors.textMuted} />
              <Text style={[styles.linkedText, { color: colors.textMuted }]}>Will auto-link on signup</Text>
            </View>
          )}
        </View>

        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{client.pending_count}</Text>
            <Text style={styles.statLabel}>{t("pending")}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{formatINR(client.current_month_amount)}</Text>
            <Text style={styles.statLabel}>{t("this_month")}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{formatINR(client.default_rate)}</Text>
            <Text style={styles.statLabel}>Rate/pc</Text>
          </View>
        </View>

        <View style={styles.filtersRow}>
          <FilterChip label="All" active={filter === "all"} onPress={() => setFilter("all")} testID="entry-filter-all" />
          <FilterChip label={t("pending")} active={filter === "pending"} onPress={() => setFilter("pending")} testID="entry-filter-pending" />
          <FilterChip label={t("returned")} active={filter === "returned"} onPress={() => setFilter("returned")} testID="entry-filter-returned" />
        </View>

        {filtered.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="shirt-outline" size={48} color={colors.textMuted} />
            <Text style={styles.emptyText}>No entries yet</Text>
            <TouchableOpacity testID="goto-add" style={styles.emptyBtn} onPress={() => router.push("/(iron)/add-entry")}>
              <Text style={styles.emptyBtnText}>{t("add_entry")}</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={{ paddingHorizontal: spacing.lg }}>
            {filtered.map((e) => (
              <View key={e.id} style={styles.entryCard} testID={`entry-${e.id}`}>
                <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
                  <View>
                    <Text style={styles.entryDate}>{formatDate(e.date_given)}</Text>
                    <Text style={styles.entryQty}>{e.total_quantity} {t("pieces")} • {e.items.length} {t("items")}</Text>
                  </View>
                  <Text style={styles.entryAmount}>{formatINR(e.total_amount)}</Text>
                </View>

                <View style={styles.itemsList}>
                  {e.items.map((it, i) => (
                    <Text key={i} style={styles.itemLine}>
                      • {it.cloth_type} × {it.quantity} @ {formatINR(it.rate)}
                    </Text>
                  ))}
                </View>

                {e.notes ? <Text style={styles.notes}>{e.notes}</Text> : null}

                <View style={styles.entryFooter}>
                  {e.status === "pending" ? (
                    <TouchableOpacity testID={`mark-returned-${e.id}`} style={styles.markBtn} onPress={() => markReturned(e.id)}>
                      <Ionicons name="checkmark-circle" size={16} color={colors.success} />
                      <Text style={styles.markBtnText}>{t("mark_returned")}</Text>
                    </TouchableOpacity>
                  ) : (
                    <View style={styles.returnedBadge}>
                      <Ionicons name="checkmark-circle" size={14} color={colors.success} />
                      <Text style={styles.returnedText}>{t("returned_on")} {formatDate(e.date_returned)}</Text>
                    </View>
                  )}
                  <TouchableOpacity testID={`delete-entry-${e.id}`} style={styles.deleteBtn} onPress={() => deleteEntry(e.id)}>
                    <Ionicons name="trash-outline" size={16} color={colors.danger} />
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function FilterChip({ label, active, onPress, testID }: { label: string; active: boolean; onPress: () => void; testID?: string }) {
  return (
    <TouchableOpacity testID={testID} style={[styles.chip, active && styles.chipActive]} onPress={onPress} activeOpacity={0.8}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: {
    flexDirection: "row", alignItems: "center", padding: spacing.lg,
    backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.borderLight,
  },
  iconBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center", borderRadius: radius.md },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: "800", color: colors.text, textAlign: "center" },

  profileBlock: { alignItems: "center", padding: spacing.xl },
  avatarBig: {
    width: 64, height: 64, borderRadius: 32,
    backgroundColor: "#EEF2FF", alignItems: "center", justifyContent: "center",
  },
  avatarBigText: { fontSize: 24, fontWeight: "800", color: colors.primary },
  clientName: { fontSize: 20, fontWeight: "800", color: colors.text, marginTop: spacing.md },
  clientPhone: { fontSize: 14, color: colors.textSecondary, marginTop: 4 },
  clientAddr: { fontSize: 12, color: colors.textMuted, textAlign: "center", marginTop: 4 },

  linkedBadge: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill,
    backgroundColor: colors.successLight, marginTop: spacing.md,
  },
  linkedText: { fontSize: 11, fontWeight: "700", color: colors.success },

  statsRow: { flexDirection: "row", gap: spacing.md, paddingHorizontal: spacing.lg, marginBottom: spacing.md },
  statCard: {
    flex: 1, padding: spacing.md, backgroundColor: colors.card, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, alignItems: "center",
  },
  statValue: { fontSize: 18, fontWeight: "800", color: colors.text },
  statLabel: { fontSize: 10, color: colors.textMuted, marginTop: 4, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5 },

  filtersRow: { flexDirection: "row", gap: 8, paddingHorizontal: spacing.lg, marginBottom: spacing.md },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 12, color: colors.textSecondary, fontWeight: "600" },
  chipTextActive: { color: colors.textInverse },

  empty: { alignItems: "center", padding: spacing.xxxl, gap: spacing.md },
  emptyText: { color: colors.textSecondary },
  emptyBtn: { backgroundColor: colors.primary, paddingHorizontal: spacing.xl, paddingVertical: 10, borderRadius: radius.pill },
  emptyBtnText: { color: colors.textInverse, fontWeight: "700" },

  entryCard: {
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.md,
  },
  entryDate: { fontSize: 14, fontWeight: "700", color: colors.text },
  entryQty: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  entryAmount: { fontSize: 18, fontWeight: "800", color: colors.primary },
  itemsList: { marginTop: spacing.md, paddingTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.borderLight },
  itemLine: { fontSize: 13, color: colors.textSecondary, marginBottom: 4 },
  notes: { fontSize: 12, color: colors.textMuted, marginTop: 8, fontStyle: "italic" },

  entryFooter: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: spacing.md },
  markBtn: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: colors.successLight, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill,
  },
  markBtnText: { fontSize: 12, color: colors.success, fontWeight: "700" },
  returnedBadge: { flexDirection: "row", alignItems: "center", gap: 4 },
  returnedText: { fontSize: 11, color: colors.success, fontWeight: "600" },
  deleteBtn: { padding: 6 },
});
