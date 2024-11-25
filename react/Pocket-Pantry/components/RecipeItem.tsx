import React, { useState } from 'react'
import { View, Text, StyleSheet, TouchableOpacity, Modal, TextInput, Pressable, Alert } from 'react-native'
import { BlurView } from 'expo-blur';
import Ionicons from '@expo/vector-icons/Ionicons';
import DateTimePicker from '@react-native-community/datetimepicker'

type RecipeProps = { // view http://47.218.196.222:8000/planned_meals?user_id=4 for more info
    recipeId: string;
    name: string;
    servings: number;
    ingredients: string[];
    ingredientUnits: string[];
    ingredientQuantities: number[];
    cookTime: number; // cook time is in minutes
    recipeSteps: string; // this is cook_steps
};
