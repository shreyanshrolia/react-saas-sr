import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "@/src/contexts/AuthContext";
import { colors } from "@/src/theme/colors";

export default function Index() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/(auth)/login");
    } else if (user.role === "iron_man") {
      router.replace("/(iron)/clients");
    } else {
      router.replace("/(client)/home");
    }
  }, [user, loading, router]);

  return (
    <View style={styles.container} testID="splash-screen">
      <Text style={styles.brand}>गृहकारी</Text>
      <Text style={styles.brandEn}>Grihkari</Text>
      <ActivityIndicator color={colors.primary} style={{ marginTop: 16 }} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
  },
  brand: {
    fontSize: 42,
    fontWeight: "700",
    color: colors.primary,
    letterSpacing: 1,
  },
  brandEn: {
    fontSize: 18,
    color: colors.textSecondary,
    marginTop: 4,
    letterSpacing: 4,
  },
});
