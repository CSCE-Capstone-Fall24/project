import React from 'react';
import { View, StyleSheet } from 'react-native';
import ShoppingItem from '@/components/ShoppingItem';

type ShoppingProps = {
  id: string;
  name: string;
  unit: string;
  quantity: number;
  checked: boolean; // Track checked state
};

type ListProps = {
  listId: string;
  userIds: string[];
  shoppingItems: ShoppingProps[];
  toggleCheckbox: (listId: string, itemId: string) => void; // Function to handle checkbox toggling
};

const ShoppingList = (props: ListProps) => {
  return (
    <View style={styles.container}>
      {props.shoppingItems.map((item) => (
        <ShoppingItem
          key={item.id}
          id={item.id}
          name={item.name}
          unit={item.unit}
          quantity={item.quantity}
          checked={item.checked}
          toggleCheckbox={() => props.toggleCheckbox(props.listId, item.id)} // Pass toggle function
        />
      ))}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginVertical: 10,
  },
});

export default ShoppingList;
