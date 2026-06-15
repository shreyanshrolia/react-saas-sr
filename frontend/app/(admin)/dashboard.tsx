import { useCallback, useEffect, useState } from "react";
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
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { adminApi, AdminUser, clearAdminToken } from "@/src/api/admin";
import { colors, radius, spacing } from "@/src/theme/colors";

export default function AdminDashboardScreen() {
  const router = useRouter();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState("");

  // Reset password modal
  const [target, setTarget] = useState<AdminUser | null>(null);
  const [newPw, setNewPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [resetErr, setResetErr] = useState("");
  const [successUser, setSuccessUser] = useState<{ name: string; phone: string; password: string } | null>(null);

  const [logoutOpen, setLogoutOpen] = useState(false);

  const fetchUsers = useCallback(async (q?: string) => {
    setErr("");
    try {
      const data = await adminApi.listUsers(q);
      setUsers(data);
    } catch (e: any) {
      if (e?.status === 401) {
        await clearAdminToken();
        router.replace("/(admin)/login");
        return;
      }
      setErr(e?.message || "Failed to load users");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [router]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => {
      setLoading(true);
      fetchUsers(query.trim() || undefined);
    }, 300);
    return () => clearTimeout(t);
  }, [query, fetchUsers]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchUsers(query.trim() || undefined);
  };

  const openReset = (u: AdminUser) => {
    setTarget(u);
    setNewPw("");
    setResetErr("");
    setShowPw(false);
  };

  const closeReset = () => {
    setTarget(null);
    setNewPw("");
    setResetErr("");
  };

  const submitReset = async () => {
    if (!target) return;
    setResetErr("");
    if (newPw.length < 6) {
      setResetErr("Password must be at least 6 characters");
      return;
    }
    setSubmitting(true);
    try {
      await adminApi.resetPassword(target.id, newPw);
      const successPayload = { name: target.name, phone: target.phone, password: newPw };
      closeReset();
      setSuccessUser(successPayload);
    } catch (e: any) {
      if (e?.status === 401) {
        await clearAdminToken();
        router.replace("/(admin)/login");
        return;
      }
      setResetErr(e?.message || "Reset failed");
    } finally {
      setSubmitting(false);
    }
  };

  const generateRandomPw = () => {
    // 8 chars, easy to read over phone: letters + digits, no confusing chars
    const chars = "abcdefghjkmnpqrstuvwxyz23456789";
    let out = "";
    for (let i = 0; i < 8; i++) out += chars[Math.floor(Math.random() * chars.length)];
    setNewPw(out);
    setShowPw(true);
  };

  const logout = () => setLogoutOpen(true);

  const confirmLogout = async () => {
    setLogoutOpen(false);
    await clearAdminToken();
    router.replace("/(admin)/login");
  };

  const roleBadge = (role: AdminUser["role"]) => {
    if (role === "iron_man") {
      return (
        <View style={[styles.badge, { backgroundColor: colors.accentLight }]}>
          <Ionicons name="shirt-outline" size={11} color={colors.accent} />
          <Text style={[styles.badgeText, { color: colors.accent }]}>Iron Man</Text>
        </View>
      );
    }
    return (
      <View style={[styles.badge, { backgroundColor: "#E0E7FF" }]}>
        <Ionicons name="person-outline" size={11} color={colors.primary} />
        <Text style={[styles.badgeText, { color: colors.primary }]}>Client</Text>
      </View>
    );
  };

  const subStatusBadge = (status?: string) => {
    if (!status) return null;
    let bg = colors.borderLight;
    let fg = colors.textSecondary;
    if (status === "trial") { bg = colors.accentLight; fg = colors.accent; }
    else if (status === "active") { bg = colors.successLight; fg = colors.success; }
    else if (status === "expired") { bg = colors.dangerLight; fg = colors.danger; }
    return (
      <View style={[styles.badge, { backgroundColor: bg }]}>
        <Text style={[styles.badgeText, { color: fg }]}>{status}</Text>
      </View>
    );
  };

  const renderItem = ({ item }: { item: AdminUser }) => (
    <View style={styles.userCard}>
      <View style={{ flex: 1 }}>
        <Text style={styles.userName} numberOfLines={1}>{item.name}</Text>
        <View style={styles.phoneRow}>
          <Ionicons name="call-outline" size={13} color={colors.textSecondary} />
          <Text style={styles.userPhone}>+91 {item.phone}</Text>
        </View>
        {item.security_question ? (
          <View style={styles.qRow}>
            <Ionicons name="help-circle-outline" size={13} color={colors.textMuted} />
            <Text style={styles.qText} numberOfLines={2}>{item.security_question}</Text>
          </View>
        ) : (
          <View style={styles.qRow}>
            <Ionicons name="alert-circle-outline" size={13} color={colors.warning} />
            <Text style={[styles.qText, { color: colors.warning }]}>No security question set</Text>
          </View>
        )}
        <View style={styles.badgeRow}>
          {roleBadge(item.role)}
          {subStatusBadge(item.subscription_status)}
        </View>
      </View>
      <TouchableOpacity
        testID={`reset-btn-${item.phone}`}
        style={styles.resetBtn}
        onPress={() => openReset(item)}
        activeOpacity={0.8}
      >
        <Ionicons name="key-outline" size={16} color={colors.textInverse} />
        <Text style={styles.resetBtnText}>Reset</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Admin Panel</Text>
          <Text style={styles.subtitle}>Helpline password reset</Text>
        </View>
        <TouchableOpacity onPress={logout} style={styles.logoutBtn} hitSlop={8} testID="admin-logout">
          <Ionicons name="log-out-outline" size={20} color={colors.danger} />
        </TouchableOpacity>
      </View>

      <View style={styles.searchWrap}>
        <Ionicons name="search-outline" size={18} color={colors.textMuted} />
        <TextInput
          testID="admin-search-input"
          value={query}
          onChangeText={setQuery}
          placeholder="Search by name or phone"
          placeholderTextColor={colors.textMuted}
          style={styles.searchInput}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="default"
        />
        {query.length > 0 && (
          <TouchableOpacity onPress={() => setQuery("")} hitSlop={8}>
            <Ionicons name="close-circle" size={18} color={colors.textMuted} />
          </TouchableOpacity>
        )}
      </View>

      {err ? (
        <View style={styles.errorBanner}>
          <Ionicons name="warning-outline" size={16} color={colors.danger} />
          <Text style={styles.errorText}>{err}</Text>
        </View>
      ) : null}

      {loading && users.length === 0 ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : (
        <FlatList
          data={users}
          keyExtractor={(u) => u.id}
          renderItem={renderItem}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxxl }}
          ItemSeparatorComponent={() => <View style={{ height: spacing.sm }} />}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="people-outline" size={48} color={colors.textMuted} />
              <Text style={styles.emptyTitle}>No users found</Text>
              <Text style={styles.emptyText}>
                {query ? `No matches for "${query}"` : "Once users sign up, they will appear here."}
              </Text>
            </View>
          }
        />
      )}

      {/* Logout confirmation modal */}
      <Modal
        visible={logoutOpen}
        animationType="fade"
        transparent
        onRequestClose={() => setLogoutOpen(false)}
      >
        <Pressable style={styles.modalBackdrop} onPress={() => setLogoutOpen(false)}>
          <Pressable style={styles.modalCard} onPress={(e) => e.stopPropagation()}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Sign out?</Text>
              <TouchableOpacity onPress={() => setLogoutOpen(false)} hitSlop={8}>
                <Ionicons name="close" size={22} color={colors.text} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalBody}>You will return to the admin login screen.</Text>
            <View style={styles.modalActions}>
              <TouchableOpacity
                testID="admin-logout-cancel"
                style={styles.secondaryBtn}
                onPress={() => setLogoutOpen(false)}
                activeOpacity={0.85}
              >
                <Text style={styles.secondaryBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                testID="admin-logout-confirm"
                style={[styles.primaryBtn, styles.dangerBtn, { flex: 1, marginTop: 0 }]}
                onPress={confirmLogout}
                activeOpacity={0.85}
              >
                <Text style={styles.primaryBtnText}>Sign out</Text>
              </TouchableOpacity>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      {/* Reset password modal */}
      <Modal
        visible={!!target}
        animationType="slide"
        transparent
        onRequestClose={closeReset}
      >
        <Pressable style={styles.modalBackdrop} onPress={closeReset}>
          <Pressable style={styles.modalCard} onPress={(e) => e.stopPropagation()}>
            <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Reset password</Text>
                <TouchableOpacity onPress={closeReset} hitSlop={8}>
                  <Ionicons name="close" size={22} color={colors.text} />
                </TouchableOpacity>
              </View>

              {target ? (
                <View style={styles.targetCard}>
                  <Text style={styles.targetName}>{target.name}</Text>
                  <Text style={styles.targetPhone}>+91 {target.phone}</Text>
                </View>
              ) : null}

              <Text style={styles.label}>New password</Text>
              <View style={styles.inputRow}>
                <Ionicons name="lock-closed-outline" size={18} color={colors.textMuted} />
                <TextInput
                  testID="admin-new-password-input"
                  value={newPw}
                  onChangeText={setNewPw}
                  placeholder="Min 6 characters"
                  placeholderTextColor={colors.textMuted}
                  secureTextEntry={!showPw}
                  style={styles.input}
                  autoCapitalize="none"
                  autoCorrect={false}
                />
                <TouchableOpacity onPress={() => setShowPw(!showPw)} hitSlop={8}>
                  <Ionicons
                    name={showPw ? "eye-off-outline" : "eye-outline"}
                    size={20}
                    color={colors.textMuted}
                  />
                </TouchableOpacity>
              </View>

              <TouchableOpacity onPress={generateRandomPw} style={styles.genBtn} activeOpacity={0.8}>
                <Ionicons name="refresh-outline" size={14} color={colors.primary} />
                <Text style={styles.genBtnText}>Generate a secure password</Text>
              </TouchableOpacity>

              {resetErr ? <Text style={styles.error}>{resetErr}</Text> : null}

              <TouchableOpacity
                testID="admin-reset-submit"
                style={[styles.primaryBtn, submitting && styles.btnDisabled]}
                onPress={submitReset}
                disabled={submitting}
                activeOpacity={0.85}
              >
                {submitting ? (
                  <ActivityIndicator color={colors.textInverse} />
                ) : (
                  <Text style={styles.primaryBtnText}>Reset password</Text>
                )}
              </TouchableOpacity>
            </KeyboardAvoidingView>
          </Pressable>
        </Pressable>
      </Modal>

      {/* Success modal */}
      <Modal
        visible={!!successUser}
        animationType="fade"
        transparent
        onRequestClose={() => setSuccessUser(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <View style={styles.successIcon}>
              <Ionicons name="checkmark-circle" size={48} color={colors.success} />
            </View>
            <Text style={styles.successTitle}>Password reset</Text>
            <Text style={styles.successSubtitle}>Share these details with the user over the helpline.</Text>

            {successUser ? (
              <View style={styles.credBox}>
                <View style={styles.credRow}>
                  <Text style={styles.credLabel}>Name</Text>
                  <Text style={styles.credValue}>{successUser.name}</Text>
                </View>
                <View style={styles.credDivider} />
                <View style={styles.credRow}>
                  <Text style={styles.credLabel}>Phone</Text>
                  <Text style={styles.credValue}>+91 {successUser.phone}</Text>
                </View>
                <View style={styles.credDivider} />
                <View style={styles.credRow}>
                  <Text style={styles.credLabel}>New password</Text>
                  <Text style={[styles.credValue, { fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" }]}>
                    {successUser.password}
                  </Text>
                </View>
              </View>
            ) : null}

            <View style={styles.warnBox}>
              <Ionicons name="information-circle-outline" size={14} color={colors.warning} />
              <Text style={styles.warnText}>
                This password will not be shown again. Ask the user to sign in and change it.
              </Text>
            </View>

            <TouchableOpacity
              testID="admin-reset-done"
              style={styles.primaryBtn}
              onPress={() => setSuccessUser(null)}
              activeOpacity={0.85}
            >
              <Text style={styles.primaryBtnText}>Done</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  title: { fontSize: 22, fontWeight: "800", color: colors.text },
  subtitle: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  logoutBtn: {
    width: 38,
    height: 38,
    borderRadius: radius.md,
    backgroundColor: colors.dangerLight,
    alignItems: "center",
    justifyContent: "center",
  },
  searchWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.card,
    marginHorizontal: spacing.lg,
    paddingHorizontal: spacing.md,
    height: 44,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  searchInput: { flex: 1, fontSize: 15, color: colors.text, height: 44 },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginHorizontal: spacing.lg,
    padding: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.dangerLight,
  },
  errorText: { color: colors.danger, fontSize: 12, flex: 1 },
  userCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: spacing.sm,
  },
  userName: { fontSize: 15, fontWeight: "700", color: colors.text },
  phoneRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 4 },
  userPhone: { fontSize: 13, color: colors.textSecondary },
  qRow: { flexDirection: "row", alignItems: "flex-start", gap: 4, marginTop: 4 },
  qText: { flex: 1, fontSize: 11, color: colors.textMuted, lineHeight: 14 },
  badgeRow: { flexDirection: "row", gap: 6, marginTop: 8, flexWrap: "wrap" },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.pill,
  },
  badgeText: { fontSize: 10, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.3 },
  resetBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: 9,
    borderRadius: radius.md,
  },
  resetBtnText: { color: colors.textInverse, fontSize: 13, fontWeight: "700" },
  empty: { alignItems: "center", padding: spacing.xxxl, gap: 8 },
  emptyTitle: { fontSize: 16, fontWeight: "700", color: colors.text, marginTop: spacing.sm },
  emptyText: { fontSize: 13, color: colors.textSecondary, textAlign: "center" },

  // Modal
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.45)",
    justifyContent: "center",
    padding: spacing.lg,
  },
  modalCard: {
    backgroundColor: colors.card,
    borderRadius: radius.xl,
    padding: spacing.xl,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  modalTitle: { fontSize: 18, fontWeight: "800", color: colors.text },
  targetCard: {
    backgroundColor: colors.inputBg,
    padding: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.lg,
  },
  targetName: { fontSize: 15, fontWeight: "700", color: colors.text },
  targetPhone: { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  label: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: 8,
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.inputBg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    height: 50,
  },
  input: { flex: 1, fontSize: 15, color: colors.text, height: 50 },
  genBtn: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: spacing.sm, alignSelf: "flex-start" },
  genBtnText: { color: colors.primary, fontSize: 12, fontWeight: "700" },
  error: { color: colors.danger, fontSize: 13, marginTop: spacing.sm, textAlign: "center" },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    height: 50,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.lg,
  },
  btnDisabled: { opacity: 0.7 },
  primaryBtnText: { color: colors.textInverse, fontSize: 15, fontWeight: "700" },

  modalBody: { fontSize: 14, color: colors.textSecondary, marginBottom: spacing.lg, lineHeight: 20 },
  modalActions: { flexDirection: "row", gap: spacing.sm, alignItems: "center" },
  secondaryBtn: {
    borderRadius: radius.lg,
    height: 50,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
    flex: 1,
  },
  secondaryBtnText: { color: colors.text, fontSize: 15, fontWeight: "700" },
  dangerBtn: { backgroundColor: colors.danger },

  // Success modal
  successIcon: { alignItems: "center", marginBottom: spacing.sm },
  successTitle: { fontSize: 20, fontWeight: "800", color: colors.text, textAlign: "center" },
  successSubtitle: { fontSize: 13, color: colors.textSecondary, textAlign: "center", marginTop: 4, marginBottom: spacing.lg },
  credBox: {
    backgroundColor: colors.inputBg,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  credRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 6 },
  credLabel: { fontSize: 12, color: colors.textSecondary, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.3 },
  credValue: { fontSize: 14, color: colors.text, fontWeight: "700", maxWidth: "65%", textAlign: "right" },
  credDivider: { height: 1, backgroundColor: colors.borderLight },
  warnBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 6,
    marginTop: spacing.md,
    padding: spacing.sm,
    backgroundColor: colors.warningLight,
    borderRadius: radius.sm,
  },
  warnText: { flex: 1, color: colors.textSecondary, fontSize: 11, lineHeight: 15 },
});
