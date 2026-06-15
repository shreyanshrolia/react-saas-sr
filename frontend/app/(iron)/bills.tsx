import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Keyboard,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Bill, type Payment } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatDate, formatINR, formatMonth } from "@/src/utils/format";
import Toast from "@/src/components/Toast";
const STATUS_COLORS: Record<Bill["status"], { bg: string; fg: string; label: string }> = {
  paid: { bg: colors.successLight, fg: colors.success, label: "Paid" },
  overpaid: { bg: "#DBEAFE", fg: colors.primary, label: "Overpaid" },
  partial: { bg: "#FEF3C7", fg: "#B45309", label: "Partial" },
  unpaid: { bg: colors.warningLight, fg: colors.warning, label: "Unpaid" },
};

export default function BillsScreen() {
  const { t } = useI18n();
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [filter, setFilter] = useState<"all" | "paid" | "unpaid">("all");
  const [query, setQuery] = useState("");
  const [selectedBill, setSelectedBill] = useState<Bill | null>(null);
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

  const filtered = bills.filter((b) => {
    const q = query.trim().toLowerCase();
    if (q && !b.client_name.toLowerCase().includes(q) && !b.client_phone.includes(q)) return false;
    if (filter === "all") return true;
    if (filter === "paid") return b.status === "paid" || b.status === "overpaid";
    return b.status === "unpaid" || b.status === "partial";
  });

  const totalUnpaid = bills
    .filter((b) => b.status === "unpaid" || b.status === "partial")
    .reduce((s, b) => s + b.balance, 0);
  const totalCollected = bills.reduce((s, b) => s + b.amount_paid, 0);

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
          {generating ? <ActivityIndicator size="small" color={colors.primary} /> : (
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
          <Text style={[styles.statLabel, { color: colors.warning }]}>To collect</Text>
        </View>
        <View style={[styles.statCard, { backgroundColor: colors.successLight }]}>
          <Text style={[styles.statValue, { color: colors.success }]}>{formatINR(totalCollected)}</Text>
          <Text style={[styles.statLabel, { color: colors.success }]}>Collected</Text>
        </View>
      </View>

      <View style={styles.filtersWrap}>
        <Chip label="All" active={filter === "all"} onPress={() => setFilter("all")} testID="filter-all" />
        <Chip label="Unpaid" active={filter === "unpaid"} onPress={() => setFilter("unpaid")} testID="filter-unpaid" />
        <Chip label="Paid" active={filter === "paid"} onPress={() => setFilter("paid")} testID="filter-paid" />
      </View>

      <View style={styles.searchWrap}>
        <Ionicons name="search" size={16} color={colors.textMuted} />
        <TextInput
          testID="bill-search-input"
          style={styles.searchInput}
          placeholder="Search by client name or phone"
          placeholderTextColor={colors.textMuted}
          value={query}
          onChangeText={setQuery}
          autoCapitalize="none"
          autoCorrect={false}
        />
        {query.length > 0 ? (
          <TouchableOpacity onPress={() => setQuery("")} testID="clear-bill-search">
            <Ionicons name="close-circle" size={16} color={colors.textMuted} />
          </TouchableOpacity>
        ) : null}
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
            <BillCard bill={item} onPress={() => setSelectedBill(item)} />
          )}
        />
      )}

      <PaymentSheet
        bill={selectedBill}
        onClose={() => setSelectedBill(null)}
        onPaymentRecorded={() => {
          setSelectedBill(null);
          load();
          setToast({ msg: "Payment recorded", variant: "success" });
        }}
      />
    </SafeAreaView>
  );
}

function BillCard({ bill, onPress }: { bill: Bill; onPress: () => void }) {
  const { t } = useI18n();
  const sc = STATUS_COLORS[bill.status];
  return (
    <TouchableOpacity
      testID={`bill-card-${bill.id}`}
      style={styles.billCard}
      onPress={onPress}
      activeOpacity={0.85}
    >
      <View style={styles.billHeaderRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.billClient}>{bill.client_name}</Text>
          <Text style={styles.billMeta}>{formatMonth(bill.month)} • {bill.total_quantity} {t("pieces")}</Text>
        </View>
        <View style={[styles.statusBadge, { backgroundColor: sc.bg }]}>
          <Text style={[styles.statusText, { color: sc.fg }]}>{sc.label}</Text>
        </View>
      </View>

      <View style={styles.breakdown}>
        <BreakdownRow label={t("clothes_amount")} value={formatINR(bill.clothes_amount)} />
        {bill.carry_in !== 0 ? (
          <BreakdownRow
            label={t("carry_forward")}
            value={`${bill.carry_in > 0 ? "+" : ""}${formatINR(bill.carry_in)}`}
            color={bill.carry_in > 0 ? colors.warning : colors.success}
          />
        ) : null}
        <BreakdownRow label={t("net_due")} value={formatINR(bill.net_due)} bold />
        <BreakdownRow label={t("amount_paid")} value={`− ${formatINR(bill.amount_paid)}`} color={colors.success} />
        <View style={styles.divider} />
        <BreakdownRow
          label={t("balance")}
          value={formatINR(Math.abs(bill.balance))}
          color={bill.balance > 0 ? colors.warning : bill.balance < 0 ? colors.primary : colors.success}
          big
        />
      </View>

      <View style={styles.cardFooter}>
        <Ionicons name="card-outline" size={14} color={colors.primary} />
        <Text style={styles.footerHint}>Tap to record payment</Text>
        <Ionicons name="chevron-forward" size={14} color={colors.textMuted} style={{ marginLeft: "auto" }} />
      </View>
    </TouchableOpacity>
  );
}

function BreakdownRow({ label, value, color, bold, big }: { label: string; value: string; color?: string; bold?: boolean; big?: boolean }) {
  return (
    <View style={styles.brRow}>
      <Text style={[styles.brLabel, big && { fontSize: 13 }]}>{label}</Text>
      <Text style={[
        styles.brValue,
        bold && { fontWeight: "800" },
        big && { fontSize: 18, fontWeight: "800" },
        color ? { color } : null,
      ]}>{value}</Text>
    </View>
  );
}

function Chip({ label, active, onPress, testID }: { label: string; active: boolean; onPress: () => void; testID?: string }) {
  return (
    <TouchableOpacity testID={testID} style={[styles.chip, active && styles.chipActive]} onPress={onPress} activeOpacity={0.8}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

function PaymentSheet({ bill, onClose, onPaymentRecorded }: { bill: Bill | null; onClose: () => void; onPaymentRecorded: () => void }) {
  const { t } = useI18n();
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [payments, setPayments] = useState<Payment[]>([]);
  const amountRef = useRef<TextInput>(null);

  const loadPayments = useCallback(async (billId: string) => {
    try {
      const p = await api.get<Payment[]>(`/bills/${billId}/payments`);
      setPayments(p);
    } catch {
      setPayments([]);
    }
  }, []);

  // Reset on bill change
  const visible = !!bill;
  const billId = bill?.id;
  useFocusEffect(useCallback(() => {
    if (billId) loadPayments(billId);
  }, [billId, loadPayments]));

  if (!bill) return null;

  const submit = async () => {
    setErr("");
    Keyboard.dismiss();
    const amt = parseFloat(amount);
    if (!amt || amt <= 0) return setErr("Enter a valid amount");
    setLoading(true);
    try {
      await api.post(`/bills/${bill.id}/payments`, { amount: amt, notes: notes.trim() || undefined });
      setAmount("");
      setNotes("");
      onPaymentRecorded();
    } catch (e: any) {
      setErr(e?.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  const payFull = () => {
    setAmount(String(Math.max(0, bill.balance).toFixed(2)));
    setTimeout(() => amountRef.current?.focus(), 50);
  };

  const deletePayment = async (pid: string) => {
    try {
      await api.delete(`/payments/${pid}`);
      await loadPayments(bill.id);
      onPaymentRecorded();
    } catch {/* ignore */}
  };

  const sc = STATUS_COLORS[bill.status];

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose} presentationStyle="pageSheet">
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top"]}>
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
          <View style={styles.psHeader}>
            <TouchableOpacity testID="close-payment-sheet" onPress={onClose} style={styles.psCloseBtn}>
              <Ionicons name="close" size={22} color={colors.text} />
            </TouchableOpacity>
            <Text style={styles.psTitle}>{t("record_payment")}</Text>
            <View style={{ width: 40 }} />
          </View>

          <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: 150 }} keyboardShouldPersistTaps="handled">
            <View style={styles.psClientCard}>
              <View style={styles.psAvatar}>
                <Text style={styles.psAvatarText}>{bill.client_name.charAt(0).toUpperCase()}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.psClientName}>{bill.client_name}</Text>
                <Text style={styles.psClientMonth}>{formatMonth(bill.month)}</Text>
              </View>
              <View style={[styles.statusBadge, { backgroundColor: sc.bg }]}>
                <Text style={[styles.statusText, { color: sc.fg }]}>{sc.label}</Text>
              </View>
            </View>

            <View style={styles.psBreakdown}>
              <BreakdownRow label={t("clothes_amount")} value={formatINR(bill.clothes_amount)} />
              {bill.carry_in !== 0 ? (
                <BreakdownRow
                  label={t("carry_forward")}
                  value={`${bill.carry_in > 0 ? "+" : ""}${formatINR(bill.carry_in)}`}
                  color={bill.carry_in > 0 ? colors.warning : colors.success}
                />
              ) : null}
              <BreakdownRow label={t("net_due")} value={formatINR(bill.net_due)} bold />
              <BreakdownRow label={t("amount_paid")} value={`− ${formatINR(bill.amount_paid)}`} color={colors.success} />
              <View style={styles.divider} />
              <BreakdownRow
                label={bill.balance < 0 ? "Overpaid" : t("balance")}
                value={formatINR(Math.abs(bill.balance))}
                color={bill.balance > 0 ? colors.warning : bill.balance < 0 ? colors.primary : colors.success}
                big
              />
            </View>

            <Text style={styles.modalLabel}>{t("payment_amount")}</Text>
            <View style={styles.inputRow}>
              <Text style={styles.prefix}>₹</Text>
              <TextInput
                ref={amountRef}
                testID="payment-amount-input"
                style={styles.inputInline}
                value={amount}
                onChangeText={(v) => setAmount(v.replace(/[^0-9.]/g, ""))}
                keyboardType="numeric"
                placeholder="0"
                placeholderTextColor={colors.textMuted}
                returnKeyType="done"
                autoFocus
              />
              {bill.balance > 0 ? (
                <TouchableOpacity testID="pay-full-button" style={styles.payFullBtn} onPress={payFull}>
                  <Text style={styles.payFullText}>{t("pay_full")}: {formatINR(bill.balance)}</Text>
                </TouchableOpacity>
              ) : null}
            </View>

            <Text style={styles.modalLabel}>{t("payment_notes")}</Text>
            <TextInput
              testID="payment-notes-input"
              style={[styles.modalInput, { height: 60, textAlignVertical: "top", paddingTop: 12 }]}
              value={notes}
              onChangeText={setNotes}
              multiline
              placeholder="Cash, UPI, etc."
              placeholderTextColor={colors.textMuted}
            />

            {err ? <Text style={styles.errorText}>{err}</Text> : null}

            <View style={styles.historyHeader}>
              <Text style={styles.modalLabel}>{t("payment_history")}</Text>
              <Text style={styles.historyCount}>{payments.length}</Text>
            </View>
            {payments.length === 0 ? (
              <Text style={styles.noPayments}>{t("no_payments")}</Text>
            ) : (
              payments.map((p) => (
                <View key={p.id} style={styles.paymentRow} testID={`payment-${p.id}`}>
                  <View style={styles.paymentIcon}>
                    <Ionicons name="cash-outline" size={16} color={colors.success} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.paymentAmount}>{formatINR(p.amount)}</Text>
                    <Text style={styles.paymentDate}>{formatDate(p.paid_at)}{p.notes ? ` • ${p.notes}` : ""}</Text>
                  </View>
                  <TouchableOpacity
                    testID={`delete-payment-${p.id}`}
                    style={styles.deletePaymentBtn}
                    onPress={() => deletePayment(p.id)}
                  >
                    <Ionicons name="trash-outline" size={14} color={colors.danger} />
                  </TouchableOpacity>
                </View>
              ))
            )}
          </ScrollView>

          <View style={styles.psFooter}>
            <TouchableOpacity
              testID="submit-payment-button"
              style={[styles.payBtn, loading && { opacity: 0.6 }]}
              onPress={submit}
              disabled={loading}
            >
              {loading ? <ActivityIndicator color={colors.textInverse} /> : (
                <>
                  <Ionicons name="checkmark-circle" size={18} color={colors.textInverse} />
                  <Text style={styles.payBtnText}>{t("save_payment")}</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
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

  filtersWrap: { flexDirection: "row", gap: 8, paddingHorizontal: spacing.xl, paddingBottom: spacing.md },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 12, color: colors.textSecondary, fontWeight: "600" },
  chipTextActive: { color: colors.textInverse },

  searchWrap: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginHorizontal: spacing.xl, marginBottom: spacing.md,
    paddingHorizontal: spacing.md, height: 42,
    backgroundColor: colors.card, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.borderLight,
  },
  searchInput: { flex: 1, fontSize: 14, color: colors.text, height: 42 },

  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  emptyText: { color: colors.textSecondary },

  billCard: {
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.md,
  },
  billHeaderRow: { flexDirection: "row", alignItems: "center" },
  billClient: { fontSize: 15, fontWeight: "700", color: colors.text },
  billMeta: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  statusText: { fontSize: 10, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.5 },

  breakdown: { marginTop: spacing.md, padding: spacing.md, backgroundColor: colors.bgSecondary, borderRadius: radius.md, gap: 6 },
  brRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  brLabel: { fontSize: 12, color: colors.textSecondary, fontWeight: "600" },
  brValue: { fontSize: 13, color: colors.text, fontWeight: "600" },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 4 },

  cardFooter: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.md, paddingTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.borderLight },
  footerHint: { fontSize: 11, color: colors.primary, fontWeight: "600" },

  // PaymentSheet
  psHeader: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.lg, paddingVertical: spacing.md,
    borderBottomWidth: 1, borderBottomColor: colors.borderLight, backgroundColor: colors.card,
  },
  psCloseBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center", borderRadius: radius.md },
  psTitle: { fontSize: 18, fontWeight: "800", color: colors.text },

  psClientCard: {
    flexDirection: "row", alignItems: "center", gap: spacing.md,
    backgroundColor: colors.card, padding: spacing.lg, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight,
  },
  psAvatar: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: "#EEF2FF", alignItems: "center", justifyContent: "center",
  },
  psAvatarText: { fontSize: 18, fontWeight: "800", color: colors.primary },
  psClientName: { fontSize: 16, fontWeight: "800", color: colors.text },
  psClientMonth: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },

  psBreakdown: {
    marginTop: spacing.lg,
    padding: spacing.lg,
    backgroundColor: colors.bgSecondary,
    borderRadius: radius.lg, gap: 6,
  },

  modalLabel: { fontSize: 12, fontWeight: "700", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5, marginTop: spacing.xl, marginBottom: 8 },
  modalInput: {
    backgroundColor: colors.inputBg, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border,
    paddingHorizontal: spacing.lg, height: 52, fontSize: 16, color: colors.text,
  },
  inputRow: {
    flexDirection: "row", alignItems: "center", backgroundColor: colors.inputBg,
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.lg, height: 52,
  },
  prefix: { color: colors.textSecondary, fontSize: 16, marginRight: 8, fontWeight: "500" },
  inputInline: { flex: 1, fontSize: 16, color: colors.text, height: 52 },

  payFullBtn: { paddingHorizontal: 10, paddingVertical: 5, backgroundColor: colors.primary, borderRadius: radius.pill, marginLeft: 6 },
  payFullText: { color: colors.textInverse, fontSize: 11, fontWeight: "700" },

  errorText: { color: colors.danger, fontSize: 13, marginTop: spacing.md, textAlign: "center" },

  historyHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  historyCount: { fontSize: 11, color: colors.textMuted, marginTop: spacing.xl, fontWeight: "700" },
  noPayments: { fontSize: 13, color: colors.textMuted, fontStyle: "italic", textAlign: "center", padding: spacing.lg },

  paymentRow: {
    flexDirection: "row", alignItems: "center", gap: spacing.md,
    padding: spacing.md, backgroundColor: colors.card,
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderLight,
    marginBottom: spacing.sm,
  },
  paymentIcon: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.successLight, alignItems: "center", justifyContent: "center",
  },
  paymentAmount: { fontSize: 15, fontWeight: "800", color: colors.text },
  paymentDate: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
  deletePaymentBtn: { padding: 6 },

  psFooter: {
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
});
