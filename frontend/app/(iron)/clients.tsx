import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Keyboard,
  KeyboardAvoidingView,
  Modal,
  Platform,
  RefreshControl,
  ScrollView,
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
import NotificationBell from "@/src/components/NotificationBell";

export default function ClientsScreen() {
  const { t } = useI18n();
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [query, setQuery] = useState("");
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
        <View style={{ flexDirection: "row", gap: 8 }}>
          <NotificationBell />
          <TouchableOpacity
            testID="open-add-client-button"
            style={styles.addBtn}
            onPress={() => setShowAdd(true)}
            activeOpacity={0.85}
          >
            <Ionicons name="add" size={24} color={colors.textInverse} />
          </TouchableOpacity>
        </View>
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
        <>
          <View style={styles.searchWrap}>
            <Ionicons name="search" size={16} color={colors.textMuted} />
            <TextInput
              testID="client-search-input"
              style={styles.searchInput}
              placeholder="Search by name or phone"
              placeholderTextColor={colors.textMuted}
              value={query}
              onChangeText={setQuery}
              autoCapitalize="none"
              autoCorrect={false}
            />
            {query.length > 0 ? (
              <TouchableOpacity onPress={() => setQuery("")} testID="clear-client-search">
                <Ionicons name="close-circle" size={16} color={colors.textMuted} />
              </TouchableOpacity>
            ) : null}
          </View>
          <FlatList
            data={clients.filter((c) => {
              const q = query.trim().toLowerCase();
              if (!q) return true;
              return c.name.toLowerCase().includes(q) || c.phone.includes(q);
            })}
            keyExtractor={(it) => it.id}
            contentContainerStyle={{ padding: spacing.lg, paddingBottom: 100 }}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
          renderItem={({ item }) => (
            <View testID={`client-card-${item.id}`} style={styles.card}>
              <TouchableOpacity
                style={styles.cardMain}
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
              </TouchableOpacity>
              <TouchableOpacity
                testID={`quick-add-entry-${item.id}`}
                style={styles.quickAddBtn}
                onPress={() => router.push(`/(iron)/add-entry?clientId=${item.id}` as any)}
                activeOpacity={0.85}
              >
                <Ionicons name="add" size={16} color={colors.primary} />
                <Text style={styles.quickAddText}>{t("quick_add_entry")}</Text>
              </TouchableOpacity>
            </View>
          )}
        />
        </>
      )}

      <AddClientModal
        visible={showAdd}
        onClose={() => setShowAdd(false)}
        onAdded={(created) => {
          setShowAdd(false);
          setToast({ msg: `${created.name} added`, variant: "success" });
          load();
          // Pre-select the just-added client when navigating to add-entry next
          // so the user can immediately start adding clothes for them.
          setTimeout(() => {
            router.push(`/(iron)/add-entry?clientId=${created.id}` as any);
          }, 500);
        }}
      />
    </SafeAreaView>
  );
}

function AddClientModal({ visible, onClose, onAdded }: { visible: boolean; onClose: () => void; onAdded: (client: Client) => void }) {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [rate, setRate] = useState("10");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const phoneRef = useRef<TextInput>(null);
  const rateRef = useRef<TextInput>(null);
  const addressRef = useRef<TextInput>(null);

  const reset = () => { setName(""); setPhone(""); setAddress(""); setRate("10"); setErr(""); };

  const submit = async () => {
    setErr("");
    Keyboard.dismiss();
    if (!name.trim()) return setErr("Please enter client name");
    if (phone.length !== 10) return setErr("Phone must be 10 digits");
    setLoading(true);
    try {
      const created = await api.post<Client>("/clients", {
        name: name.trim(),
        phone,
        address: address.trim() || undefined,
        default_rate: parseFloat(rate) || 10,
      });
      reset();
      onAdded(created);
    } catch (e: any) {
      setErr(e?.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose} presentationStyle="pageSheet">
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top"]}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 20}
        >
          <View style={styles.fsHeader}>
            <TouchableOpacity testID="close-add-client" onPress={() => { reset(); onClose(); }} style={styles.fsCloseBtn}>
              <Ionicons name="close" size={22} color={colors.text} />
            </TouchableOpacity>
            <Text style={styles.fsTitle}>{t("add_client")}</Text>
            <View style={{ width: 40 }} />
          </View>

          <ScrollView
            style={{ flex: 1 }}
            contentContainerStyle={styles.fsContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <View style={styles.intro}>
              <View style={styles.introIcon}>
                <Ionicons name="person-add" size={24} color={colors.primary} />
              </View>
              <Text style={styles.introTitle}>New Client</Text>
              <Text style={styles.introSub}>
                Phone is the unique key. If they sign up later, they will auto-link.
              </Text>
            </View>

            <Text style={styles.modalLabel}>{t("client_name")} *</Text>
            <TextInput
              testID="add-client-name-input"
              style={styles.modalInput}
              value={name}
              onChangeText={setName}
              placeholder="e.g. Ramesh Sharma"
              placeholderTextColor={colors.textMuted}
              returnKeyType="next"
              autoFocus
              autoCapitalize="words"
              blurOnSubmit={false}
              onSubmitEditing={() => phoneRef.current?.focus()}
            />

            <Text style={styles.modalLabel}>{t("phone")} *</Text>
            <View style={styles.inputRow}>
              <Text style={styles.prefix}>+91</Text>
              <TextInput
                ref={phoneRef}
                testID="add-client-phone-input"
                style={styles.inputInline}
                value={phone}
                onChangeText={(v) => setPhone(v.replace(/\D/g, ""))}
                keyboardType="phone-pad"
                maxLength={10}
                placeholder="9876543210"
                placeholderTextColor={colors.textMuted}
                returnKeyType="next"
                blurOnSubmit={false}
                onSubmitEditing={() => rateRef.current?.focus()}
              />
            </View>
            <Text style={styles.modalHelp}>10 digits, no country code</Text>

            <Text style={styles.modalLabel}>{t("default_rate")}</Text>
            <View style={styles.inputRow}>
              <Text style={styles.prefix}>₹</Text>
              <TextInput
                ref={rateRef}
                testID="add-client-rate-input"
                style={styles.inputInline}
                value={rate}
                onChangeText={(v) => setRate(v.replace(/[^0-9.]/g, ""))}
                keyboardType="numeric"
                placeholder="10"
                placeholderTextColor={colors.textMuted}
                returnKeyType="next"
                blurOnSubmit={false}
                onSubmitEditing={() => addressRef.current?.focus()}
              />
              <Text style={styles.suffix}>per piece</Text>
            </View>

            <Text style={styles.modalLabel}>{t("address")}</Text>
            <TextInput
              ref={addressRef}
              testID="add-client-address-input"
              style={[styles.modalInput, { height: 90, textAlignVertical: "top", paddingTop: 12 }]}
              value={address}
              onChangeText={setAddress}
              multiline
              placeholder="House no, street, area..."
              placeholderTextColor={colors.textMuted}
              returnKeyType="done"
              onSubmitEditing={submit}
            />

            {err ? <Text style={styles.errorText}>{err}</Text> : null}
          </ScrollView>

          <View style={styles.fsFooter}>
            <TouchableOpacity
              testID="submit-add-client"
              style={[styles.primaryBtnFull, loading && { opacity: 0.6 }]}
              onPress={submit}
              disabled={loading}
              activeOpacity={0.85}
            >
              {loading ? (
                <ActivityIndicator color={colors.textInverse} />
              ) : (
                <>
                  <Ionicons name="checkmark" size={18} color={colors.textInverse} />
                  <Text style={styles.primaryBtnText}>{t("save")}</Text>
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
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    marginBottom: spacing.md,
    borderWidth: 1, borderColor: colors.borderLight,
    overflow: "hidden",
  },
  cardMain: {
    flexDirection: "row", alignItems: "center",
    padding: spacing.lg,
  },
  quickAddBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4,
    paddingVertical: 10, backgroundColor: "#EEF2FF",
    borderTopWidth: 1, borderTopColor: colors.borderLight,
  },
  quickAddText: { color: colors.primary, fontWeight: "700", fontSize: 13 },
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

  searchWrap: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginHorizontal: spacing.xl, marginBottom: spacing.md,
    paddingHorizontal: spacing.md, height: 42,
    backgroundColor: colors.card, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.borderLight,
  },
  searchInput: { flex: 1, fontSize: 14, color: colors.text, height: 42 },

  // modal
  modalBackdrop: { flex: 1, backgroundColor: "rgba(15, 23, 42, 0.4)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: colors.card, borderTopLeftRadius: radius.xxl, borderTopRightRadius: radius.xxl,
    padding: spacing.xl, paddingBottom: spacing.xxxl,
  },
  sheetHandle: { width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: "center", marginBottom: spacing.md },
  sheetTitle: { fontSize: 20, fontWeight: "800", color: colors.text, marginBottom: spacing.lg },
  modalLabel: { fontSize: 12, fontWeight: "600", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6, marginTop: spacing.md },
  modalHelp: { fontSize: 11, color: colors.textMuted, marginTop: 4, marginLeft: 2 },
  modalInput: {
    backgroundColor: colors.inputBg, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border,
    paddingHorizontal: spacing.lg, height: 52, fontSize: 16, color: colors.text,
  },
  inputRow: {
    flexDirection: "row", alignItems: "center", backgroundColor: colors.inputBg,
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.lg, height: 52,
  },
  prefix: { color: colors.textSecondary, fontSize: 16, marginRight: 8, fontWeight: "500" },
  suffix: { color: colors.textMuted, fontSize: 13, marginLeft: 8 },
  inputInline: { flex: 1, fontSize: 16, color: colors.text, height: 52 },
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
  primaryBtnFull: {
    flexDirection: "row", gap: 6,
    backgroundColor: colors.primary, borderRadius: radius.lg, height: 54,
    alignItems: "center", justifyContent: "center",
    shadowColor: colors.primary, shadowOpacity: 0.25, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 4,
  },
  primaryBtnText: { color: colors.textInverse, fontWeight: "700", fontSize: 16 },

  // full-screen add-client modal
  fsHeader: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.lg, paddingVertical: spacing.md,
    borderBottomWidth: 1, borderBottomColor: colors.borderLight, backgroundColor: colors.card,
  },
  fsCloseBtn: { width: 40, height: 40, alignItems: "center", justifyContent: "center", borderRadius: radius.md },
  fsTitle: { fontSize: 18, fontWeight: "800", color: colors.text },
  fsContent: { padding: spacing.xl, paddingBottom: spacing.xxxl * 2 },
  fsFooter: {
    padding: spacing.lg, backgroundColor: colors.card,
    borderTopWidth: 1, borderTopColor: colors.borderLight,
  },

  intro: { alignItems: "center", marginBottom: spacing.xl },
  introIcon: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: "#EEF2FF", alignItems: "center", justifyContent: "center", marginBottom: spacing.md,
  },
  introTitle: { fontSize: 20, fontWeight: "800", color: colors.text },
  introSub: { fontSize: 13, color: colors.textSecondary, textAlign: "center", marginTop: 4, paddingHorizontal: spacing.xl },
});
