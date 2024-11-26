import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";

type MealProps = {
  meal_id: string;
  user_id: string;
  recipe_id: string;
  n_servings: number;
  is_shared: boolean;
  shared_with: Number[];
  expiration: Date;
  recipe: any; // lol
};

const MealItem = (props: MealProps) => {
  const { recipe_id, n_servings, is_shared, shared_with, expiration } = props;

  return (
    <TouchableOpacity style={styles.container} onPress={() => console.log("Meal pressed:", recipe_id)}>
      <View style={styles.textContainer}>
        {/* Meal Info */}
        <Text style={styles.recipeName}>{props.recipe.name}</Text>
        <Text style={styles.details}>Servings: {n_servings}</Text>
        <Text style={styles.details}>Expiration: {expiration.toLocaleDateString()}</Text>

        {/* Sharing Info */}
        {is_shared && (
          <Text style={styles.shared}>
            Shared with {shared_with.length} {shared_with.length === 1 ? "person" : "people"}
          </Text>
        )}
      </View>

      {/* Icon */}
      <View style={styles.iconContainer}>
        <Ionicons name="fast-food-outline" size={32} color="gray" />
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    height: 100,
    marginVertical: 8,
    marginHorizontal: 16,
    borderRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 5,
    elevation: 5,
    shadowColor: "black",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#FFF",
    padding: 16,
  },
  textContainer: {
    flex: 1,
  },
  recipeName: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#333",
    marginBottom: 4,
  },
  details: {
    fontSize: 14,
    color: "#555",
    marginBottom: 2,
  },
  shared: {
    fontSize: 14,
    color: "#2a9d8f",
    marginTop: 4,
  },
  iconContainer: {
    paddingLeft: 16,
  },
});

export default MealItem;
