import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Client } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatINR } from "@/src/utils/format";
import Toast from "@/src/components/Toast";

export default function ClientsScreen() {
  const { t } = useI18n();
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [toast, setToast] = useState<{ msg: string; variant?: "success" | "error" } | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get<Client[]>("/clients");
      setClients(data);
    } catch (e: any) {
      setToast({ msg: e?.message || "Failed to load", variant: "error" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const onRefresh = () => { setRefreshing(true); load(); };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast visible={!!toast} message={toast?.msg || ""} variant={toast?.variant} onHide={() => setToast(null)} />
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>{t("your_clients")}</Text>
          <Text style={styles.subtitle}>{clients.length} {clients.length === 1 ? "client" : "clients"}</Text>
        </View>
        <TouchableOpacity
          testID="open-add-client-button"
          style={styles.addBtn}
          onPress={() => setShowAdd(true)}
          activeOpacity={0.85}
        >
          <Ionicons name="add" size={24} color={colors.textInverse} />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : clients.length === 0 ? (
        <View style={styles.empty}>
          <View style={styles.emptyIcon}>
            <Ionicons name="people-outline" size={40} color={colors.primary} />
          </View>
          <Text style={styles.emptyText}>{t("no_clients")}</Text>
          <TouchableOpacity testID="empty-add-client" style={styles.emptyBtn} onPress={() => setShowAdd(true)}>
            <Ionicons name="add" size={18} color={colors.textInverse} />
            <Text style={styles.emptyBtnText}>{t("add_client")}</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={clients}
          keyExtractor={(it) => it.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
          renderItem={({ item }) => (
            <TouchableOpacity
              testID={`client-card-${item.id}`}
              style={styles.card}
              onPress={() => router.push(`/(iron)/client/${item.id}` as any)}
              activeOpacity={0.85}
            >
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>{item.name.charAt(0).toUpperCase()}</Text>
                {item.linked_user_id ? <View style={styles.linkedDot} /> : null}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.cardName}>{item.name}</Text>
                <Text style={styles.cardPhone}>+91 {item.phone}</Text>
                <View style={styles.metaRow}>
                  {item.pending_count > 0 ? (
                    <View style={styles.pendingBadge}>
                      <Ionicons name="time-outline" size={12} color={colors.warning} />
                      <Text style={styles.pendingText}>{item.pending_count} {t("pending")}</Text>
                    </View>
                  ) : null}
                </View>
              </View>
              <View style={styles.cardRight}>
                <Text style={styles.amount}>{formatINR(item.current_month_amount)}</Text>
                <Text style={styles.amountLabel}>{t("this_month")}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
            </TouchableOpacity>
          )}
        />
      )}

      <AddClientModal
        visible={showAdd}
        onClose={() => setShowAdd(false)}
        onAdded={() => {
          setShowAdd(false);
          setToast({ msg: t("success"), variant: "success" });
          load();
        }}
      />
    </SafeAreaView>
  );
}

function AddClientModal({ visible, onClose, onAdded }: { visible: boolean; onClose: () => void; onAdded: () => void }) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [rate, setRate] = useState("10");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const reset = () => { setName(""); setPhone(""); setAddress(""); setRate("10"); setErr(""); };

  const submit = async () => {
    setErr("");
    if (!name.trim()) return setErr(t("client_name"));
    if (phone.length !== 10) return setErr(t("phone_help"));
    setLoading(true);
    try {
      await api.post("/clients", { name: name.trim(), phone, address: address.trim() || undefined, default_rate: parseFloat(rate) || 10 });
      reset();
      onAdded();
    } catch (e: any) {
      setErr(e?.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.modalBackdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
            <View style={styles.sheetHandle} />
            <Text style={styles.sheetTitle}>{t("add_client")}</Text>

            <Text style={styles.modalLabel}>{t("client_name")}</Text>
            <TextInput
              testID="add-client-name-input"
              style={styles.modalInput}
              value={name}
              onChangeText={setName}
              placeholder={t("client_name")}
              placeholderTextColor={colors.textMuted}
            />

            <Text style={styles.modalLabel}>{t("phone")}</Text>
            <View style={styles.inputRow}>
              <Text style={styles.prefix}>+91</Text>
              <TextInput
                testID="add-client-phone-input"
                style={styles.inputInline}
                value={phone}
                onChangeText={(v) => setPhone(v.replace(/\D/g, ""))}
                keyboardType="phone-pad"
                maxLength={10}
                placeholder="9876543210"
                placeholderTextColor={colors.textMuted}
              />
            </View>

            <Text style={styles.modalLabel}>{t("default_rate")}</Text>
            <TextInput
              testID="add-client-rate-input"
              style={styles.modalInput}
              value={rate}
              onChangeText={(v) => setRate(v.replace(/[^0-9.]/g, ""))}
              keyboardType="numeric"
              placeholder="10"
              placeholderTextColor={colors.textMuted}
            />

            <Text style={styles.modalLabel}>{t("address")}</Text>
            <TextInput
              testID="add-client-address-input"
              style={[styles.modalInput, { height: 70, textAlignVertical: "top", paddingTop: 12 }]}
              value={address}
              onChangeText={setAddress}
              multiline
              placeholder={t("address")}
              placeholderTextColor={colors.textMuted}
            />

            {err ? <Text style={styles.errorText}>{err}</Text> : null}

            <View style={styles.sheetActions}>
              <TouchableOpacity testID="cancel-add-client" style={styles.secondaryBtn} onPress={() => { reset(); onClose(); }}>
                <Text style={styles.secondaryBtnText}>{t("cancel")}</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="submit-add-client" style={[styles.primaryBtn, { flex: 1 }]} onPress={submit} disabled={loading}>
                {loading ? <ActivityIndicator color={colors.textInverse} /> : <Text style={styles.primaryBtnText}>{t("save")}</Text>}
              </TouchableOpacity>
            </View>
          </KeyboardAvoidingView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
  },
  title: { fontSize: 26, fontWeight: "800", color: colors.text },
  subtitle: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  addBtn: {
    width: 44, height: 44, borderRadius: radius.lg, backgroundColor: colors.primary,
    alignItems: "center", justifyContent: "center",
    shadowColor: colors.primary, shadowOpacity: 0.25, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 4,
  },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.xxxl },
  emptyIcon: {
    width: 80, height: 80, borderRadius: 40, backgroundColor: "#EEF2FF",
    alignItems: "center", justifyContent: "center", marginBottom: spacing.lg,
  },
  emptyText: { fontSize: 15, color: colors.textSecondary, textAlign: "center", marginBottom: spacing.xl },
  emptyBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: colors.primary, paddingHorizontal: spacing.xl, paddingVertical: 12, borderRadius: radius.pill,
  },
  emptyBtnText: { color: colors.textInverse, fontWeight: "700" },
  card: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.card, padding: spacing.lg,
    borderRadius: radius.lg, marginBottom: spacing.md,
    borderWidth: 1, borderColor: colors.borderLight,
  },
  avatar: {
    width: 48, height: 48, borderRadius: radius.md,
    backgroundColor: "#EEF2FF", alignItems: "center", justifyContent: "center",
    marginRight: spacing.md,
  },
  avatarText: { fontSize: 18, fontWeight: "700", color: colors.primary },
  linkedDot: {
    position: "absolute", bottom: 2, right: 2,
    width: 10, height: 10, borderRadius: 5, backgroundColor: colors.success,
    borderWidth: 2, borderColor: colors.card,
  },
  cardName: { fontSize: 15, fontWeight: "700", color: colors.text },
  cardPhone: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  metaRow: { flexDirection: "row", gap: 6, marginTop: 6 },
  pendingBadge: {
    flexDirection: "row", alignItems: "center", gap: 4,
    backgroundColor: colors.warningLight, paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.pill,
  },
  pendingText: { fontSize: 11, color: colors.warning, fontWeight: "600" },
  cardRight: { alignItems: "flex-end", marginRight: 6 },
  amount: { fontSize: 15, fontWeight: "700", color: colors.text },
  amountLabel: { fontSize: 10, color: colors.textMuted, marginTop: 2 },

  // modal
  modalBackdrop: { flex: 1, backgroundColor: "rgba(15, 23, 42, 0.4)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: colors.card, borderTopLeftRadius: radius.xxl, borderTopRightRadius: radius.xxl,
    padding: spacing.xl, paddingBottom: spacing.xxxl,
  },
  sheetHandle: { width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: "center", marginBottom: spacing.md },
  sheetTitle: { fontSize: 20, fontWeight: "800", color: colors.text, marginBottom: spacing.lg },
  modalLabel: { fontSize: 12, fontWeight: "600", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6, marginTop: spacing.md },
  modalInput: {
    backgroundColor: colors.inputBg, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border,
    paddingHorizontal: spacing.lg, height: 48, fontSize: 15, color: colors.text,
  },
  inputRow: {
    flexDirection: "row", alignItems: "center", backgroundColor: colors.inputBg,
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.lg, height: 48,
  },
  prefix: { color: colors.textSecondary, fontSize: 15, marginRight: 8, fontWeight: "500" },
  inputInline: { flex: 1, fontSize: 15, color: colors.text, height: 48 },
  errorText: { color: colors.danger, fontSize: 13, marginTop: spacing.md, textAlign: "center" },
  sheetActions: { flexDirection: "row", gap: spacing.md, marginTop: spacing.xl },
  secondaryBtn: {
    paddingHorizontal: spacing.xl, height: 48, borderRadius: radius.md,
    alignItems: "center", justifyContent: "center", backgroundColor: colors.bgSecondary,
  },
  secondaryBtnText: { color: colors.text, fontWeight: "700" },
  primaryBtn: {
    backgroundColor: colors.primary, borderRadius: radius.md, height: 48,
    alignItems: "center", justifyContent: "center",
  },
  primaryBtnText: { color: colors.textInverse, fontWeight: "700", fontSize: 15 },
});
