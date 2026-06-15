import React, { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, Text, View } from "react-native";
import { colors, radius, spacing } from "@/src/theme/colors";
import { Ionicons } from "@expo/vector-icons";

type Variant = "success" | "error" | "info";

interface Props {
  visible: boolean;
  message: string;
  variant?: Variant;
  onHide?: () => void;
}

export default function Toast({ visible, message, variant = "info", onHide }: Props) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translate = useRef(new Animated.Value(-20)).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
        Animated.timing(translate, { toValue: 0, duration: 200, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
      ]).start();
      const t = setTimeout(() => {
        Animated.parallel([
          Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }),
          Animated.timing(translate, { toValue: -20, duration: 200, useNativeDriver: true }),
        ]).start(() => onHide?.());
      }, 2200);
      return () => clearTimeout(t);
    }
  }, [visible, opacity, translate, onHide]);

  if (!visible) return null;

  const bg = variant === "success" ? colors.successLight : variant === "error" ? colors.dangerLight : "#DBEAFE";
  const fg = variant === "success" ? colors.success : variant === "error" ? colors.danger : colors.primary;
  const icon = variant === "success" ? "checkmark-circle" : variant === "error" ? "alert-circle" : "information-circle";

  return (
    <Animated.View
      pointerEvents="none"
      style={[styles.wrap, { opacity, transform: [{ translateY: translate }] }]}
    >
      <View style={[styles.toast, { backgroundColor: bg }]}>
        <Ionicons name={icon as any} size={18} color={fg} />
        <Text style={[styles.text, { color: fg }]} numberOfLines={2}>{message}</Text>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    top: 60,
    left: 0,
    right: 0,
    alignItems: "center",
    zIndex: 1000,
    elevation: 1000,
  },
  toast: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radius.pill,
    maxWidth: "90%",
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowOffset: { width: 0, height: 4 },
    shadowRadius: 8,
    elevation: 4,
  },
  text: { fontSize: 13, fontWeight: "600", flexShrink: 1 },
});
