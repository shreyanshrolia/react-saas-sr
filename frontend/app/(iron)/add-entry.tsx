import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { api, type Client, type EntryItem } from "@/src/api/client";
import { useI18n } from "@/src/i18n/I18nContext";
import { colors, radius, spacing } from "@/src/theme/colors";
import { formatINR } from "@/src/utils/format";
import Toast from "@/src/components/Toast";

const DEFAULT_TYPES = ["Shirt", "Pant", "Saree", "Kurta", "Bedsheet", "Other"];

export default function AddEntryScreen() {
  const { t } = useI18n();
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [selected, setSelected] = useState<Client | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [items, setItems] = useState<EntryItem[]>([{ cloth_type: "Shirt", quantity: 1, rate: 10 }]);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [toast, setToast] = useState<{ msg: string; variant?: "success" | "error" } | null>(null);

  const loadClients = useCallback(async () => {
    try {
      const data = await api.get<Client[]>("/clients");
      setClients(data);
      if (data.length > 0 && !selected) {
        setSelected(data[0]);
        setItems((cur) => cur.map((it) => ({ ...it, rate: it.rate || data[0].default_rate })));
      }
    } catch (e: any) {
      setToast({ msg: e?.message || "Failed", variant: "error" });
    }
  }, [selected]);

  useEffect(() => {
    loadClients();
  }, [loadClients]);

  const total = items.reduce((s, it) => s + (it.quantity || 0) * (it.rate || 0), 0);
  const totalQty = items.reduce((s, it) => s + (it.quantity || 0), 0);

  const updateItem = (idx: number, patch: Partial<EntryItem>) => {
    setItems((cur) => cur.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  };

  const addItem = () => {
    const rate = selected?.default_rate || 10;
    setItems((cur) => [...cur, { cloth_type: "Shirt", quantity: 1, rate }]);
  };

  const removeItem = (idx: number) => {
    if (items.length === 1) return;
    setItems((cur) => cur.filter((_, i) => i !== idx));
  };

  const submit = async () => {
    setErr("");
    if (!selected) return setErr(t("select_client"));
    if (items.some((it) => !it.cloth_type.trim() || it.quantity <= 0 || it.rate < 0)) {
      return setErr(t("error"));
    }
    setLoading(true);
    try {
      await api.post("/entries", { client_id: selected.id, items, notes: notes.trim() || undefined });
      setItems([{ cloth_type: "Shirt", quantity: 1, rate: selected.default_rate || 10 }]);
      setNotes("");
      setToast({ msg: t("success"), variant: "success" });
      setTimeout(() => router.push("/(iron)/clients"), 600);
    } catch (e: any) {
      setErr(e?.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <Toast visible={!!toast} message={toast?.msg || ""} variant={toast?.variant} onHide={() => setToast(null)} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: 120 }}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.title}>{t("new_entry")}</Text>

          <Text style={styles.label}>{t("select_client")}</Text>
          <TouchableOpacity
            testID="select-client-button"
            style={styles.clientPicker}
            onPress={() => setPickerOpen(true)}
            activeOpacity={0.8}
          >
            {selected ? (
              <>
                <View style={styles.avatar}><Text style={styles.avatarText}>{selected.name.charAt(0).toUpperCase()}</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.clientPickerName}>{selected.name}</Text>
                  <Text style={styles.clientPickerPhone}>+91 {selected.phone}</Text>
                </View>
              </>
            ) : (
              <Text style={styles.clientPlaceholder}>{clients.length === 0 ? t("no_clients") : t("select_client")}</Text>
            )}
            <Ionicons name="chevron-down" size={18} color={colors.textMuted} />
          </TouchableOpacity>

          <View style={{ marginTop: spacing.xl }}>
            <Text style={styles.label}>{t("items")}</Text>
            {items.map((item, idx) => (
              <View key={idx} style={styles.itemRow} testID={`item-row-${idx}`}>
                <View style={{ flex: 1 }}>
                  <View style={styles.chipsRow}>
                    {DEFAULT_TYPES.map((typ) => (
                      <TouchableOpacity
                        key={typ}
                        testID={`item-${idx}-type-${typ}`}
                        style={[styles.chip, item.cloth_type === typ && styles.chipActive]}
                        onPress={() => updateItem(idx, { cloth_type: typ })}
                      >
                        <Text style={[styles.chipText, item.cloth_type === typ && styles.chipTextActive]}>{typ}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                  {item.cloth_type === "Other" || !DEFAULT_TYPES.includes(item.cloth_type) ? (
                    <TextInput
                      testID={`item-${idx}-custom-type`}
                      style={styles.input}
                      placeholder={t("cloth_type")}
                      placeholderTextColor={colors.textMuted}
                      value={DEFAULT_TYPES.includes(item.cloth_type) ? "" : item.cloth_type}
                      onChangeText={(v) => updateItem(idx, { cloth_type: v })}
                    />
                  ) : null}

                  <View style={styles.qtyRateRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.miniLabel}>{t("quantity")}</Text>
                      <View style={styles.stepper}>
                        <TouchableOpacity testID={`item-${idx}-qty-minus`} style={styles.stepBtn} onPress={() => updateItem(idx, { quantity: Math.max(1, item.quantity - 1) })}>
                          <Ionicons name="remove" size={18} color={colors.primary} />
                        </TouchableOpacity>
                        <TextInput
                          testID={`item-${idx}-qty-input`}
                          style={styles.stepInput}
                          value={String(item.quantity)}
                          keyboardType="numeric"
                          onChangeText={(v) => updateItem(idx, { quantity: parseInt(v || "0", 10) || 0 })}
                        />
                        <TouchableOpacity testID={`item-${idx}-qty-plus`} style={styles.stepBtn} onPress={() => updateItem(idx, { quantity: item.quantity + 1 })}>
                          <Ionicons name="add" size={18} color={colors.primary} />
                        </TouchableOpacity>
                      </View>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.miniLabel}>{t("rate")}</Text>
                      <View style={styles.rateInputWrap}>
                        <Text style={styles.rupee}>₹</Text>
                        <TextInput
                          testID={`item-${idx}-rate-input`}
                          style={styles.rateInput}
                          value={String(item.rate)}
                          keyboardType="numeric"
                          onChangeText={(v) => updateItem(idx, { rate: parseFloat(v || "0") || 0 })}
                        />
                      </View>
                    </View>
                    <View style={{ alignItems: "flex-end" }}>
                      <Text style={styles.miniLabel}>{t("total")}</Text>
                      <Text style={styles.itemTotal}>{formatINR(item.quantity * item.rate)}</Text>
                    </View>
                  </View>
                </View>
                {items.length > 1 ? (
                  <TouchableOpacity testID={`item-${idx}-remove`} style={styles.removeBtn} onPress={() => removeItem(idx)}>
                    <Ionicons name="close" size={16} color={colors.danger} />
                  </TouchableOpacity>
                ) : null}
              </View>
            ))}

            <TouchableOpacity testID="add-item-button" style={styles.addItemBtn} onPress={addItem}>
              <Ionicons name="add-circle-outline" size={18} color={colors.primary} />
              <Text style={styles.addItemText}>{t("add_item")}</Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.label}>{t("notes")}</Text>
          <TextInput
            testID="entry-notes-input"
            style={[styles.input, { height: 70, textAlignVertical: "top", paddingTop: 12 }]}
            multiline
            value={notes}
            onChangeText={setNotes}
            placeholder={t("notes")}
            placeholderTextColor={colors.textMuted}
          />

          {err ? <Text style={styles.error}>{err}</Text> : null}
        </ScrollView>

        <View style={styles.footer}>
          <View style={{ flex: 1 }}>
            <Text style={styles.footerLabel}>{totalQty} {t("pieces")}</Text>
            <Text style={styles.footerTotal}>{formatINR(total)}</Text>
          </View>
          <TouchableOpacity
            testID="save-entry-button"
            style={[styles.saveBtn, (loading || !selected) && styles.btnDisabled]}
            onPress={submit}
            disabled={loading || !selected}
          >
            {loading ? <ActivityIndicator color={colors.textInverse} /> : (
              <>
                <Ionicons name="checkmark" size={18} color={colors.textInverse} />
                <Text style={styles.saveBtnText}>{t("save_entry")}</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>

      <Modal visible={pickerOpen} transparent animationType="slide" onRequestClose={() => setPickerOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setPickerOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={styles.sheetHandle} />
            <Text style={styles.sheetTitle}>{t("select_client")}</Text>
            <ScrollView style={{ maxHeight: 400 }}>
              {clients.map((c) => (
                <TouchableOpacity
                  key={c.id}
                  testID={`picker-client-${c.id}`}
                  style={[styles.pickerItem, selected?.id === c.id && styles.pickerItemActive]}
                  onPress={() => {
                    setSelected(c);
                    setItems((cur) => cur.map((it) => ({ ...it, rate: it.rate || c.default_rate })));
                    setPickerOpen(false);
                  }}
                >
                  <View style={styles.avatar}><Text style={styles.avatarText}>{c.name.charAt(0).toUpperCase()}</Text></View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.clientPickerName}>{c.name}</Text>
                    <Text style={styles.clientPickerPhone}>+91 {c.phone}</Text>
                  </View>
                  {selected?.id === c.id ? <Ionicons name="checkmark-circle" size={20} color={colors.primary} /> : null}
                </TouchableOpacity>
              ))}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  title: { fontSize: 24, fontWeight: "800", color: colors.text, marginBottom: spacing.lg },
  label: {
    fontSize: 12, fontWeight: "600", color: colors.textSecondary,
    textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8, marginTop: spacing.md,
  },
  clientPicker: {
    flexDirection: "row", alignItems: "center", gap: spacing.md,
    backgroundColor: colors.card, padding: spacing.md, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.border,
  },
  clientPlaceholder: { flex: 1, color: colors.textMuted, fontSize: 14 },
  clientPickerName: { fontSize: 15, fontWeight: "700", color: colors.text },
  clientPickerPhone: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  avatar: {
    width: 40, height: 40, borderRadius: radius.md,
    backgroundColor: "#EEF2FF", alignItems: "center", justifyContent: "center",
  },
  avatarText: { fontSize: 15, fontWeight: "700", color: colors.primary },

  itemRow: {
    backgroundColor: colors.card, padding: spacing.md, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.borderLight, marginBottom: spacing.md,
    flexDirection: "row", gap: 8,
  },
  chipsRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill,
    backgroundColor: colors.bgSecondary, borderWidth: 1, borderColor: colors.borderLight,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 12, color: colors.textSecondary, fontWeight: "600" },
  chipTextActive: { color: colors.textInverse },

  qtyRateRow: { flexDirection: "row", gap: spacing.md, marginTop: spacing.md, alignItems: "flex-end" },
  miniLabel: { fontSize: 10, color: colors.textMuted, marginBottom: 4, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5 },
  stepper: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.inputBg, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.border, height: 40,
  },
  stepBtn: { width: 36, height: 40, alignItems: "center", justifyContent: "center" },
  stepInput: { flex: 1, textAlign: "center", fontSize: 15, color: colors.text, fontWeight: "700" },

  rateInputWrap: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.inputBg, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.md, height: 40,
  },
  rupee: { color: colors.textSecondary, marginRight: 4, fontSize: 14 },
  rateInput: { flex: 1, fontSize: 15, color: colors.text, fontWeight: "600", height: 40 },
  itemTotal: { fontSize: 15, fontWeight: "700", color: colors.primary },

  removeBtn: {
    width: 24, height: 24, borderRadius: 12,
    backgroundColor: colors.dangerLight, alignItems: "center", justifyContent: "center",
  },

  input: {
    backgroundColor: colors.inputBg, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border,
    paddingHorizontal: spacing.lg, height: 44, fontSize: 14, color: colors.text, marginTop: 8,
  },

  addItemBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
    paddingVertical: 12, borderRadius: radius.md, backgroundColor: "#EEF2FF",
  },
  addItemText: { color: colors.primary, fontWeight: "700" },

  error: { color: colors.danger, fontSize: 13, marginTop: spacing.md, textAlign: "center" },

  footer: {
    position: "absolute", bottom: 0, left: 0, right: 0,
    backgroundColor: colors.card, borderTopWidth: 1, borderTopColor: colors.borderLight,
    flexDirection: "row", alignItems: "center", padding: spacing.lg, gap: spacing.md,
  },
  footerLabel: { fontSize: 11, color: colors.textMuted, textTransform: "uppercase", letterSpacing: 0.5 },
  footerTotal: { fontSize: 22, fontWeight: "800", color: colors.text, marginTop: 2 },
  saveBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: colors.primary, paddingHorizontal: spacing.xl, height: 48, borderRadius: radius.md,
    justifyContent: "center",
  },
  saveBtnText: { color: colors.textInverse, fontWeight: "700", fontSize: 14 },
  btnDisabled: { opacity: 0.6 },

  backdrop: { flex: 1, backgroundColor: "rgba(15, 23, 42, 0.4)", justifyContent: "flex-end" },
  sheet: { backgroundColor: colors.card, borderTopLeftRadius: radius.xxl, borderTopRightRadius: radius.xxl, padding: spacing.lg, paddingBottom: spacing.xxxl },
  sheetHandle: { width: 40, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: "center", marginBottom: spacing.md },
  sheetTitle: { fontSize: 18, fontWeight: "800", color: colors.text, marginBottom: spacing.md },
  pickerItem: {
    flexDirection: "row", alignItems: "center", gap: spacing.md,
    padding: spacing.md, borderRadius: radius.md, marginBottom: 4,
  },
  pickerItemActive: { backgroundColor: "#EEF2FF" },
});
