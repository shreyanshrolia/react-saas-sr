import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Bill, type Entry, type IronManLink } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { currentMonthKey, formatDate, formatINR } from "@/src/utils/format";

type Filter = "all" | "pending" | "returned";

export default function ClientHome() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [ironMen, setIronMen] = useState<IronManLink[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");

  const load = useCallback(async () => {
    try {
      const [im, en, bi] = await Promise.all([
        api.get<IronManLink[]>("/my/iron-men"),
        api.get<Entry[]>("/entries"),
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
  const pendingCount = entries.filter((e) => e.status === "pending").length;
  const returnedCount = entries.filter((e) => e.status === "returned").length;

  const filteredEntries = entries.filter((e) =>
    filter === "all" ? true : e.status === filter,
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: 100 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); load(); }}
            tintColor={colors.primary}
          />
        }
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
                <View style={[styles.heroPill, { backgroundColor: "rgba(254, 226, 226, 0.95)" }]}>
                  <View style={[styles.dot, { backgroundColor: colors.danger }]} />
                  <Text style={[styles.heroPillText, { color: colors.danger }]}>{pendingCount} {t("pending")}</Text>
                </View>
                <View style={[styles.heroPill, { backgroundColor: "rgba(220, 252, 231, 0.95)" }]}>
                  <View style={[styles.dot, { backgroundColor: colors.success }]} />
                  <Text style={[styles.heroPillText, { color: colors.success }]}>{returnedCount} {t("returned")}</Text>
                </View>
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
                  <TouchableOpacity
                    key={im.iron_man_id}
                    style={styles.imCard}
                    testID={`im-card-${im.iron_man_id}`}
                    activeOpacity={0.85}
                    onPress={() => Linking.openURL(`tel:${im.iron_man_phone}`)}
                  >
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
                  </TouchableOpacity>
                ))
              )}
            </View>

            <View style={styles.section}>
              <View style={styles.recordsHeader}>
                <Text style={styles.sectionTitle}>{t("your_clothes")}</Text>
                <Text style={styles.recordsCount}>{entries.length} total</Text>
              </View>

              {/* Filter chips */}
              <View style={styles.filtersRow}>
                <FilterChip
                  label={`All (${entries.length})`}
                  active={filter === "all"}
                  onPress={() => setFilter("all")}
                  testID="record-filter-all"
                />
                <FilterChip
                  label={`${t("pending")} (${pendingCount})`}
                  active={filter === "pending"}
                  onPress={() => setFilter("pending")}
                  testID="record-filter-pending"
                  accent="danger"
                />
                <FilterChip
                  label={`${t("returned")} (${returnedCount})`}
                  active={filter === "returned"}
                  onPress={() => setFilter("returned")}
                  testID="record-filter-returned"
                  accent="success"
                />
              </View>

              {filteredEntries.length === 0 ? (
                <View style={styles.emptyCard}>
                  <Ionicons name="shirt-outline" size={32} color={colors.textMuted} />
                  <Text style={styles.emptyText}>No records to show</Text>
                </View>
              ) : (
                filteredEntries.map((e) => <EntryCard key={e.id} entry={e} t={t} />)
              )}
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function FilterChip({
  label,
  active,
  onPress,
  testID,
  accent,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  testID?: string;
  accent?: "danger" | "success";
}) {
  const activeBg = accent === "danger" ? colors.danger : accent === "success" ? colors.success : colors.primary;
  return (
    <TouchableOpacity
      testID={testID}
      style={[styles.chip, active && { backgroundColor: activeBg, borderColor: activeBg }]}
      onPress={onPress}
      activeOpacity={0.8}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

function EntryCard({ entry, t }: { entry: Entry; t: (k: any) => string }) {
  const isReturned = entry.status === "returned";
  return (
    <View
      style={[
        styles.entryCard,
        {
          borderLeftColor: isReturned ? colors.success : colors.danger,
          backgroundColor: isReturned ? "rgba(220, 252, 231, 0.35)" : "rgba(254, 226, 226, 0.35)",
        },
      ]}
      testID={`record-${entry.id}`}
    >
      <View style={styles.entryHeader}>
        <View style={{ flex: 1 }}>
          <Text style={styles.entryDate}>{formatDate(entry.date_given)}</Text>
          <Text style={styles.entrySub}>
            {entry.total_quantity} {t("pieces")} • {entry.items.length} {t("items")}
          </Text>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: isReturned ? colors.success : colors.danger }]}>
          <Ionicons
            name={isReturned ? "checkmark-circle" : "time"}
            size={12}
            color={colors.textInverse}
          />
          <Text style={styles.statusText}>
            {isReturned ? t("returned") : t("pending")}
          </Text>
        </View>
      </View>

      <View style={styles.itemsList}>
        {entry.items.map((it, i) => (
          <View key={i} style={styles.itemPill}>
            <Text style={styles.itemPillText}>
              {it.cloth_type} × {it.quantity}
            </Text>
            <Text style={styles.itemPillRate}>@ {formatINR(it.rate)}</Text>
          </View>
        ))}
      </View>

      <View style={styles.entryFooter}>
        <View style={{ flex: 1 }}>
          {isReturned && entry.date_returned ? (
            <Text style={styles.returnedLine}>
              {t("returned_on")} {formatDate(entry.date_returned)}
            </Text>
          ) : (
            <Text style={[styles.returnedLine, { color: colors.danger }]}>
              Not received yet
            </Text>
          )}
          {entry.notes ? <Text style={styles.notes}>{entry.notes}</Text> : null}
        </View>
        <Text style={styles.entryAmount}>{formatINR(entry.total_amount)}</Text>
      </View>
    </View>
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
  heroPill: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill },
  dot: { width: 8, height: 8, borderRadius: 4 },
  heroPillText: { fontSize: 12, fontWeight: "700" },

  section: { paddingHorizontal: spacing.lg, marginTop: spacing.lg },
  sectionTitle: { fontSize: 12, fontWeight: "700", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: spacing.md },
  recordsHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  recordsCount: { fontSize: 11, color: colors.textMuted, fontWeight: "600" },

  filtersRow: { flexDirection: "row", gap: 8, marginBottom: spacing.md, flexWrap: "wrap" },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  chipText: { fontSize: 12, color: colors.textSecondary, fontWeight: "600" },
  chipTextActive: { color: colors.textInverse },

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

  // Entry/record card
  entryCard: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderLeftWidth: 5,
    borderWidth: 1,
    borderColor: colors.borderLight,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  entryHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  entryDate: { fontSize: 15, fontWeight: "800", color: colors.text },
  entrySub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  statusBadge: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill,
  },
  statusText: { fontSize: 11, fontWeight: "800", color: colors.textInverse },
  itemsList: {
    flexDirection: "row", flexWrap: "wrap", gap: 6,
    marginTop: spacing.md, paddingTop: spacing.md,
    borderTopWidth: 1, borderTopColor: colors.borderLight,
  },
  itemPill: {
    flexDirection: "row", gap: 6,
    backgroundColor: colors.card, paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border,
  },
  itemPillText: { fontSize: 12, fontWeight: "700", color: colors.text },
  itemPillRate: { fontSize: 11, color: colors.textMuted },

  entryFooter: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.md },
  returnedLine: { fontSize: 11, color: colors.success, fontWeight: "600" },
  notes: { fontSize: 11, color: colors.textMuted, fontStyle: "italic", marginTop: 2 },
  entryAmount: { fontSize: 18, fontWeight: "800", color: colors.primary },
});
