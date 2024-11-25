# IMPORTS 
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import or_, and_, any_, not_, cast, Integer, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import NoResultFound

from itertools import combinations
from datetime import datetime
import copy

from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr
from fuzzywuzzy import fuzz, process

from database import get_db
from models import Recipes, Users, PlannedMeals, Pantry

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# HELPER FUNCTIONS -------------------------------------------------------------------------

GRAMS_CONVERSION = {
    # Volume to grams (based on water density)
    "cup": 240, "cups": 240, "c": 240,
    "tablespoon": 15, "tablespoons": 15, "tbsp": 15, "tbs": 15, "Tbl": 15, "T": 15,
    "teaspoon": 5, "teaspoons": 5, "tsp": 5,
    "ml": 1, "milliliter": 1, "milliliters": 1, "cc": 1,
    "l": 1000, "liter": 1000, "liters": 1000, "litre": 1000, "litres": 1000,
    "fl oz": 30, "fluid ounce": 30, "fluid ounces": 30,
    "pint": 473, "pints": 473, "pt": 473,
    "quart": 946, "quarts": 946, "qt": 946,
    "gallon": 3785, "gallons": 3785, "gal": 3785,
    "drop": 0.05, "drops": 0.05, "gtt": 0.05,
    "dash": 0.6, "dashes": 0.6,
    "pinch": 0.3, "pinches": 0.3,
    "handful": 30, "handfuls": 30,  

    # Weight to grams
    "gram": 1, "grams": 1, "g": 1, "gm": 1,
    "kilogram": 1000, "kilograms": 1000, "kg": 1000,
    "milligram": 0.001, "milligrams": 0.001, "mg": 0.001,
    "ounce": 28, "ounces": 28, "oz": 28,
    "pound": 454, "pounds": 454, "lb": 454, "lbs": 454,
    "stone": 6350, "stones": 6350, "st": 6350,

    # Miscellaneous (approximate based on common usage)
    "clove": 5, "cloves": 5,  
    "slice": 30, "slices": 30,  
    "stick": 113, "sticks": 113, 
    "can": 400, "cans": 400,  
    "bottle": 500, "bottles": 500,  
    "pack": 500, "packs": 500, "pkt": 500, "packet": 500, "packets": 500,
    "bunch": 150, "bunches": 150,  
    "piece": 100, "pieces": 100, "pc": 100,  
    "leaf": 1, "leaves": 1,  
    "sprig": 1, "sprigs": 1  
}

def convert_to_grams(quantity, unit_name):
    if unit_name in GRAMS_CONVERSION:
        return quantity * GRAMS_CONVERSION[unit_name]
    raise ValueError(f"Unit '{unit_name}' is not recognized")

def convert_from_grams(quantity, unit_name):
    if unit_name in GRAMS_CONVERSION:
        return quantity / GRAMS_CONVERSION[unit_name]
    raise ValueError(f"Unit '{unit_name}' is not recognized")

def convert_list_to_grams(quantities, unit_names):
    if len(quantities) != len(unit_names):
        raise ValueError("The number of quantities must match the number of unit names")
    converted_quantities = []
    for quantity, unit_name in zip(quantities, unit_names):
        if unit_name in GRAMS_CONVERSION:
            converted_quantities.append(quantity * GRAMS_CONVERSION[unit_name])
        else:
            raise ValueError(f"Unit '{unit_name}' is not recognized")
    return converted_quantities

def convert_list_from_grams(quantities, unit_names):
    if len(quantities) != len(unit_names):
        raise ValueError("The number of quantities must match the number of unit names")
    converted_quantities = []
    for quantity, unit_name in zip(quantities, unit_names):
        if unit_name in GRAMS_CONVERSION:
            converted_quantities.append(quantity / GRAMS_CONVERSION[unit_name])
        else:
            raise ValueError(f"Unit '{unit_name}' is not recognized")
    return converted_quantities
    

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace '*' with specific origins like ['http://localhost:19000'] for stricter access
    allow_credentials=True,
    allow_methods=["*"],  # HTTP methods allowed (e.g., ['GET', 'POST', 'PUT'])
    allow_headers=["*"],  # HTTP headers allowed (e.g., ['Content-Type', 'Authorization'])
)

@app.get("/")
async def root():
    return {"message": "Hello World"}


# GENERAL QUERIES --------------------------------------------------------------------------------------------------------------

@app.get("/all_recipes")
def all_recipes(db: Session = Depends(get_db)):

    all_r = db.query(Recipes).all()
    return all_r

@app.get("/all_users")
def all_users(db: Session = Depends(get_db)):

    all_u = db.query(Users).all()
    return all_u

@app.get("/user")
def single_user(user_id: int, db: Session = Depends(get_db)):

    all_u = db.query(Users).filter(Users.user_id == user_id).all()
    return all_u

@app.get("/all_pantry")
def all_pantry(db: Session = Depends(get_db)):

    all_p = db.query(Pantry).all()
    return all_p

@app.get("/all_meals")
def all_meals(db: Session = Depends(get_db)):

    all_m = db.query(PlannedMeals).all()
    return all_m


# PANTRY QUERIES ----------------------------------------------------------------------------------------

@app.get("/indv_pantry")
def get_user_pantry(user_id: int, db: Session = Depends(get_db)):
    user_pantry = db.query(Pantry).filter(Pantry.user_id == user_id).all()

    if not user_pantry:
        raise HTTPException(status_code=404, detail="No pantry items found for this user")

    return user_pantry

@app.get("/whole_pantry/")
def get_pantry_items(user_id: int, db: Session = Depends(get_db)):
    pantry_items = db.query(Pantry).filter(
        or_(
            Pantry.user_id == user_id,
            and_(
                Pantry.is_shared == True,
                user_id == any_(Pantry.shared_with)
            )
        )
    ).all()

    return pantry_items

class UserList(BaseModel):
    user_list: List[int]

@app.post("/unique_pantry_multiple_users/")
def multi_user_pantry_items(data: UserList, db: Session = Depends(get_db)):
    pantry_items = db.query(Pantry).filter(
        or_(
            Pantry.user_id.in_(data.user_list),
            and_(
                #Pantry.is_shared == True,
                Pantry.shared_with.op('&&')(data.user_list)
            )
        )
    ).all()
    
    if not pantry_items:
        raise HTTPException(status_code=404, detail="No pantry items found for given criteria.")
    
    return pantry_items

class ShareItemRequest(BaseModel):
    pantry_id: int
    roommate_id: int

@app.post("/share_item/")
def mark_pantry_item_shared(data: ShareItemRequest, db: Session = Depends(get_db)):
    item = db.query(Pantry).filter(Pantry.pantry_id == data.pantry_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="item not found")

    if data.roommate_id in item.shared_with:
        raise HTTPException(status_code=400, detail="item already shared with roommate")

    updated_roommates = item.shared_with + [data.roommate_id]
    item.shared_with = updated_roommates

    item.is_shared = True

    db.commit()
    db.refresh(item)
    return {"message": "Roommate added to item successfully", "pantry_id": data.pantry_id, "updated_roommates": item.shared_with}
   
@app.post("/unshare_item/")
def mark_pantry_item_unshared(data: ShareItemRequest, db: Session = Depends(get_db)):
    item = db.query(Pantry).filter(Pantry.pantry_id == data.pantry_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="item not found")

    try:
    #     idx = user.roommates.index(data.roommate_id)
        idx = item.shared_with.index(data.roommate_id)
        splice = item.shared_with[:idx] + item.shared_with[idx + 1:]
        item.shared_with = splice

        if len(splice) == 0:
            item.is_shared = False

        db.commit()
        db.refresh(item)
        return {"message": "Roommate removed successfully", "pantry_id": data.pantry_id, "updated_roommates": item.shared_with}
    
    except ValueError:
        return {"message": "roommate not shared with"}
    
class PantryItemCreate(BaseModel):
    food_name: str
    quantity: float
    unit: str
    user_id: Optional[int] = None
    added_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    category: Optional[str] = None
    comment: Optional[str] = None
    is_shared: Optional[bool] = False
    shared_with: Optional[List[int]] = Field(default_factory=list)
    location: Optional[str] = None
    price: Optional[float] = None

@app.post("/add_item/")
async def add_pantry_item(item: PantryItemCreate, db: Session = Depends(get_db)):
    pantry_item = Pantry(
        food_name=item.food_name,
        quantity=item.quantity,
        unit=item.unit,
        user_id=item.user_id,
        added_date=item.added_date or datetime.now,
        expiration_date=item.expiration_date,
        category=item.category,
        comment=item.comment,
        is_shared=item.is_shared,
        shared_with=item.shared_with,
        location=item.location,
        price=item.price
    )

    db.add(pantry_item)
    db.commit()
    db.refresh(pantry_item)

    return pantry_item

class UpdatePantryItemRequest(BaseModel):
    id: int  # Unique ID of the pantry item to update
    food_name: Optional[str] = None  
    unit: Optional[str] = None  
    user_id: int  
    added_date: Optional[datetime] = None  
    expiration_date: Optional[datetime] = None 
    category: Optional[str] = None  
    comment: Optional[str] = None  
    is_shared: Optional[bool] = None  
    shared_with: Optional[List[int]] = Field(default_factory=list)  
    location: Optional[str] = None  
    price: Optional[float] = None  

@app.put("/update_pantry_item/")
async def update_pantry_item(request: UpdatePantryItemRequest, db: Session = Depends(get_db)):
    # Fetch the pantry item to update
    pantry_item = db.query(Pantry).filter(Pantry.id == request.id, Pantry.user_id == request.user_id).first()

    if not pantry_item:
        raise HTTPException(status_code=404, detail="Pantry item not found or you do not have permission to update it.")

    # Update pantry item fields if provided in the request
    pantry_item.food_name = request.food_name if request.food_name else pantry_item.food_name
    pantry_item.quantity = request.quantity if request.quantity is not None else pantry_item.quantity
    pantry_item.unit = request.unit if request.unit else pantry_item.unit
    pantry_item.added_date = request.added_date if request.added_date else pantry_item.added_date
    pantry_item.expiration_date = request.expiration_date if request.expiration_date else pantry_item.expiration_date
    pantry_item.category = request.category if request.category else pantry_item.category
    pantry_item.comment = request.comment if request.comment else pantry_item.comment
    pantry_item.is_shared = request.is_shared if request.is_shared is not None else pantry_item.is_shared
    pantry_item.shared_with = request.shared_with if request.shared_with else pantry_item.shared_with
    pantry_item.location = request.location if request.location else pantry_item.location
    pantry_item.price = request.price if request.price is not None else pantry_item.price

    db.commit()

    return {"message": "Pantry item updated successfully", "item_id": pantry_item.id}


class RemovePantryItemRequest(BaseModel):
    id: int  # ID of the pantry item to remove
    user_id: int  # ID of the user requesting the removal

@app.put("/remove_pantry_item/")
async def remove_pantry_item(request: RemovePantryItemRequest, db: Session = Depends(get_db)):
    # Fetch the pantry item to remove
    pantry_item = db.query(Pantry).filter(Pantry.id == request.id, Pantry.user_id == request.user_id).first()

    if not pantry_item:
        raise HTTPException(status_code=404, detail="Pantry item not found or you do not have permission to remove it.")

    # Remove the pantry item
    db.delete(pantry_item)
    db.commit()

    return {"message": "Pantry item removed successfully", "item_id": request.id}
    
# MEAL QUERIES --------------------------------------------------------------------------------------------------------------

@app.get("/indv_planned_meals")
def indv_planned_meals(user_id: int, db: Session = Depends(get_db)):
    user_meals = db.query(PlannedMeals).options(joinedload(PlannedMeals.recipe)).filter(PlannedMeals.user_id == user_id).all()

    if not user_meals:
        raise HTTPException(status_code=404, detail="No planned meals found for this user")

    return user_meals

@app.get("/planned_meals")
def planned_meals(user_id: int, db: Session = Depends(get_db)):
    all_meals = db.query(PlannedMeals).options(joinedload(PlannedMeals.recipe)).filter(
        or_(
            PlannedMeals.user_id == user_id,
            and_(
                PlannedMeals.is_shared == True,
                user_id == any_(PlannedMeals.shared_with)
            )
        )
    ).all()

    return all_meals

@app.get("/meals_shared_with")
def meals_shared_with(user_id: int, db: Session = Depends(get_db)):
    shared_meals = db.query(PlannedMeals).options(joinedload(PlannedMeals.recipe)).filter(
        and_(
            PlannedMeals.is_shared == True,
            user_id == any_(PlannedMeals.shared_with)
        )
    ).all()

    return shared_meals

class PlannedMealRequest(BaseModel):
    user_id: int
    recipe_id: int
    n_servings: float
    is_shared: bool
    shared_with: List[int]

@app.post("/add_planned_meal/")
def add_planned_meal(data: PlannedMealRequest, db: Session = Depends(get_db)):
    new_meal = PlannedMeals(
        user_id=data.user_id,
        recipe_id=data.recipe_id,
        n_servings=data.n_servings,
        is_shared=data.is_shared,
        shared_with=data.shared_with
    )

    db.add(new_meal)
    db.commit()
    db.refresh(new_meal)
    return {"message": "Meal added successfully", "meal": new_meal}


class ShareMealRequest(BaseModel):
    meal_id: int
    roommate_id: int

@app.post("/share_meal/")
def share_meal(data: ShareMealRequest, db: Session = Depends(get_db)):
    meal = db.query(PlannedMeals).filter(PlannedMeals.meal_id == data.meal_id).first()
    
    if not meal:
        raise HTTPException(status_code=404, detail="meal not found")

    if data.roommate_id in meal.shared_with:
        raise HTTPException(status_code=400, detail="meal already shared with roommate")

    updated_roommates = meal.shared_with + [data.roommate_id]
    meal.shared_with = updated_roommates

    meal.is_shared = True

    db.commit()
    db.refresh(meal)
    return {"message": "Roommate added to meal successfully", "meal_id": data.meal_id, "updated_roommates": meal.shared_with}
   
@app.post("/unshare_meal/")
def mark_pantry_item_unshared(data: ShareMealRequest, db: Session = Depends(get_db)):
    meal = db.query(PlannedMeals).filter(PlannedMeals.meal_id == data.meal_id).first()
    
    if not meal:
        raise HTTPException(status_code=404, detail="meal not found")

    try:
    #     idx = user.roommates.index(data.roommate_id)
        idx = meal.shared_with.index(data.roommate_id)
        splice = meal.shared_with[:idx] + meal.shared_with[idx + 1:]
        meal.shared_with = splice

        if len(splice) == 0:
            meal.is_shared = False

        db.commit()
        db.refresh(meal)
        return {"message": "Roommate removed successfully", "meal_id": data.meal_id, "updated_roommates": meal.shared_with}
    
    except ValueError:
        return {"message": "roommate not shared with"}
    
@app.post("/delete_planned_meal/")
async def delete_planned_meal(meal_id: int, db: Session = Depends(get_db)):

    meal = db.query(PlannedMeals).filter(PlannedMeals.meal_id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Planned Meal not found")
    
    db.delete(meal)
    db.commit()

    return {"message": "Your meal has been removed and meal plan has been updated."}

#adjust item quantities after cooking meals
@app.post("/mark_meal_cooked/")
async def mark_meal_cooked(meal_id: int, db: Session = Depends(get_db)):
    
    #fetches the cooked meal from cooked meal table
    cookedMeal = db.query(PlannedMeals).filter(PlannedMeals.meal_id == meal_id).first()

    if not cookedMeal:
        raise HTTPException(status_code=404, detail="Planned Meal not found")

    #list of users on the shared meal
    user_list = []
    user_list.append(cookedMeal.user_id)

    for user in cookedMeal.shared_with:
        user_list.append(user)   
    
    #fetches the pantry items of all the users on the cooked meal
    pantry_items = db.query(Pantry).filter(
        or_(
            Pantry.user_id.in_(user_list),
            and_(
                Pantry.is_shared == True,
                Pantry.shared_with.op('&&')(user_list)
            )
        )
    ).all()

    #fetches details(Recipe Entry) for the cooked meal (ingredients: units & quantities)
    cookedMealDetails = db.query(Recipes).filter(Recipes.recipe_id == cookedMeal.recipe_id).first()

    if not cookedMealDetails:
        raise HTTPException(status_code=404, detail="Recipe not in Recipes")

    #deep copies the quantities of the planned meal
    quantities_scaled_and_converted = []
    quantities_scaled_and_converted = cookedMealDetails.ingredient_quantities
    #scale the quantities based on servings planned with servings for 
    quantities_scaled_and_converted = [item * (cookedMeal.n_servings/cookedMealDetails.serving_size) for item in quantities_scaled_and_converted]
    
    #convert units to grams
    #fetch ingredient units for the cooked meal
    units_cooked_ingredients = []
    units_cooked_ingredients = cookedMealDetails.ingredient_units

    #convert to grams for quantity adjustment
    for i in range(len(units_cooked_ingredients)):
        quantities_scaled_and_converted[i] = convert_to_grams( quantities_scaled_and_converted[i], units_cooked_ingredients[i])
    
    #fuzzy match on ingredient names - identifies corresponding ingredients in pantry from the cooking users
        #deep copy of relevant ingredient names for parallel listing with their quantities
    corresponding_ingredients_from_pantry = []  # Stores the ingredient matching names in parallel with IDs and quantities
    corresponding_pantry_item_ids = []
    corresponding_pantry_item_quantities = []
    corresponding_pantry_item_units = []
    locs_of_ingredients_not_possessed = []

    count = 0
    for meal_ingredient in cookedMealDetails.ingredients:
        best_ratio = 0
        current_best_matches = []  # Temporary list to store items with the best ratio for the current ingredient

        # Loop over pantry items
        for pantry_item in pantry_items:
            ratio = fuzz.ratio(meal_ingredient.lower(), pantry_item.food_name.lower())

            if ratio > best_ratio:  # New best match
                best_ratio = ratio
                current_best_matches = [pantry_item]  # Replace with the new best match list

            elif ratio == best_ratio:  # Add duplicates with the same best ratio
                current_best_matches.append(pantry_item)

        #if no match because item never added to pantry
        if not current_best_matches:
            locs_of_ingredients_not_possessed.append(count)
        else:
        # Append all current best matches to the corresponding lists
            for match in current_best_matches:
                corresponding_ingredients_from_pantry.append(meal_ingredient)
                corresponding_pantry_item_ids.append(match.pantry_id)
                corresponding_pantry_item_quantities.append(match.quantity)
                corresponding_pantry_item_units.append(match.unit)
        count+=1

    if current_best_matches:
        for i in reversed(locs_of_ingredients_not_possessed):
            quantities_scaled_and_converted.remove(quantities_scaled_and_converted[i])

    #convert relevant ingredient quantities to grams on the copy
    for i in range(len(corresponding_pantry_item_quantities)):
        corresponding_pantry_item_quantities[i] = convert_to_grams(corresponding_pantry_item_quantities[i], corresponding_pantry_item_units[i])

    #adjust quantities - logic for identifying multiple instances and decrementing one and then on the other
    for i in range(len(quantities_scaled_and_converted)):
        quantity_tracker = quantities_scaled_and_converted[i]
        ingredient_name = cookedMealDetails.ingredients[i]

        for j in range(len(corresponding_pantry_item_quantities)):
            if ingredient_name == corresponding_ingredients_from_pantry[j]:
                if corresponding_pantry_item_quantities[j] < quantity_tracker:
                    quantity_tracker -= corresponding_pantry_item_quantities[j]
                    corresponding_pantry_item_quantities[j] = 0
                else:
                    corresponding_pantry_item_quantities -= quantity_tracker
                    quantity_tracker = 0

            if quantity_tracker == 0:
                break

    #remove items from pantry that are now 0
    for i in range(len(corresponding_pantry_item_quantities)):
        if corresponding_pantry_item_quantities[i] == 0:
            pantry_item = db.query(Pantry).filter(Pantry.pantry_id == corresponding_pantry_item_ids[i]).first()

            if not pantry_item:
                raise HTTPException(status_code=404, detail="Pantry item not found. Line 707")

            db.delete(pantry_item)
    db.commit()

    #convert back to original unit quantities
    for i in range(len(corresponding_pantry_item_quantities)):
        reset_quantity = convert_from_grams(corresponding_pantry_item_quantities[i], corresponding_pantry_item_units[i])
        corresponding_pantry_item_quantities[i] = reset_quantity
 
    #update user pantry quanities with current deep copy list
    for i in range(len(corresponding_pantry_item_ids)):
        if corresponding_pantry_item_quantities[i] != 0:
            pantry_item = db.query(Pantry).filter(Pantry.pantry_id == corresponding_pantry_item_ids[i]).first()

            if not pantry_item:
                raise HTTPException(status_code=404, detail="Pantry item not found. Line 723")
            
            pantry_item.quantity = corresponding_pantry_item_quantities[i]

            db.refresh(pantry_item)

    #remove cooked meal from planned
    db.delete(cookedMeal)

    db.commit()
    return {"message": "Your pantry inventory has been updated and meal removed."}


# USER AND ROOMMATE QUERIES ----------------------------------------------------------------------------------

class RoommateRequest(BaseModel):
    user_id: int
    roommate_id: int

@app.post("/add_roommate/")
def add_roommate(data: RoommateRequest, db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.user_id == data.user_id).first()
    
    if not user: # should always be there if valid ui
        raise HTTPException(status_code=404, detail="User not found")

    if user.roommates is None:
        user.roommates = []

    if data.roommate_id in user.roommates:
        raise HTTPException(status_code=400, detail="Roommate already added")

    updated_roommates = user.roommates + [data.roommate_id]
    user.roommates = updated_roommates

    db.commit()
    db.refresh(user)
    return {"message": "Roommate added successfully", "user_id": data.user_id, "updated_roommates": user.roommates}
   
@app.post("/remove_roommate/")
def remove_roomate(data: RoommateRequest, db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.user_id == data.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.roommates is None:
        return {"message": "You have no roommates", "user_id": data.user_id}
    
    try:
        idx = user.roommates.index(data.roommate_id)
        splice = user.roommates[:idx] + user.roommates[idx + 1:]
        user.roommates = splice

        db.commit()
        db.refresh(user)
        return {"message": "Roommate removed successfully", "user_id": data.user_id, "updated_roommates": user.roommates}
    
    except ValueError:
        return {"message": "User not found in your roommates"}
    
class UserLogin(BaseModel):
    username: str = None
    email: str = None
    password: str

@app.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    if not data.username and not data.email:
        raise HTTPException(status_code=400, detail="Username or email is required.")

    query = db.query(Users).filter(
        (Users.username == data.username) | (Users.email == data.email)
    )

    user = query.first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if data.password != user.hashed_confirmation_code:
    # if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password.")

    return {"user_id": user.user_id}

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

@app.post("/signup")
def signup(data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(Users).filter(
        (Users.username == data.username) | (Users.email == data.email)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists.")
    
    # hashed_password = hash_password(data.password)
    hashed_password = data.password
    
    new_user = Users(
        username=data.username,
        email=data.email,
        hashed_confirmation_code=hashed_password,
        account_created_at=datetime.now(),
        roommates=[],
        favorite_recipes=[],
        cooked_recipes=[]
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully", "user_id": new_user.user_id}


# RECIPE QUERIES ----------------------------------------------------------------------------------------------------------------------------
@app.post("/recipes_made_from_inventory/")
async def recipes_from_users_inventory(data: UserList, db: Session = Depends(get_db)):
    pantry_items = db.query(Pantry).filter(
        or_(
            Pantry.user_id.in_(data.user_list),
            and_(
                #Pantry.is_shared == True,
                Pantry.shared_with.op('&&')(data.user_list)
            )
        )
    ).all()
    
    if not pantry_items:
        raise HTTPException(status_code=404, detail="No pantry items found for user.")
    
    all_r = db.query(Recipes).all()         #fetches all recipes from database

    #fuzzy matching of ingredients to pantry items
    matched_recipes_ids = []                    #return value; stores the recipes (recipe.recipe_id) that can be cooked

    # Extract pantry ingredient names (normalized to lowercase for case-insensitive comparison)
    pantry_ingredients = [p_item.food_name.lower() for p_item in pantry_items]

    for recipe in all_r:  # Iterate through each recipe in the database
        r_ingredients = [r_item.lower() for r_item in recipe.ingredients]  # Normalize recipe ingredients to lowercase

        # Check if all ingredients in the recipe have a match in pantry items
        all_match = all(
            any(fuzz.ratio(r_ingredient, p_item) > 70 for p_item in pantry_ingredients)
            for r_ingredient in r_ingredients
        )

        if all_match:  # If all ingredients are matched, add the recipe ID
            matched_recipes_ids.append(recipe.recipe_id)
    
    #Check held quantities are large enough to create recipe
    can_make_recipes_ids = []

    if len(matched_recipes_ids) > 0:
        #use matched_recipes_ids to locate 
        for id in matched_recipes_ids:
            recipe_details = db.query(Recipes).filter(Recipes.recipe_id == id).first()
            
            can_make = True
            for idx_ingredient, ingredient_name in enumerate(recipe_details.ingredients):
                # true false list for ingredients
                for item in pantry_items:

                    if fuzz.ratio(item.food_name.lower(), ingredient_name.lower()) > 70:
                        if convert_to_grams(item.quantity, item.unit) < convert_to_grams(recipe_details.ingredient_quantities[idx_ingredient], recipe_details.ingredient_units[idx_ingredient]):
                            can_make = False
            if can_make:
                can_make_recipes_ids.append(id)

    if len(can_make_recipes_ids) > 0:
        return {
            "message": "These recipes can be made with your current pantry!",
            "recipe data": db.query(Recipes).filter(Recipes.recipe_id.in_(can_make_recipes_ids)).all()
        }
    else:
        
        all_r = db.query(Recipes).all()

        ingredients_owned_all_r = []

        for recipe in all_r:
            has_ingredients = []

            for idx_ingredient, ingredient_name in enumerate(recipe.ingredients):
                possessed = False
                for item in pantry_items:
                    if fuzz.ratio(item.food_name.lower(), ingredient_name.lower()) > 70:
                        if convert_to_grams(item.quantity, item.unit) >= convert_to_grams(recipe.ingredient_quantities[idx_ingredient], recipe.ingredient_units[idx_ingredient]):
                            possessed = True
                            has_ingredients.append(True)
                            break
                if possessed == False:
                    has_ingredients.append(False)
            ingredients_owned_all_r.append(has_ingredients)


        for i, recp in enumerate(all_r):
            recp.possessed_list = ingredients_owned_all_r[i]

        all_r.sort(key = lambda recipe: sum(1 for has in recipe.possessed_list if has == False))

        all_r = all_r[:20] #keeps only the top 20 options

        return {
            "message": "Cannot fully craft any recipes with current inventory. Here are the best 20 recipes with the least missing ingredients.",
            "recipe data": all_r
        }
#ingredients possessed or not in field 'possessed_list' as a parallel list of booleans

class AddFavoriteRequest(BaseModel):
    user_id: int  # ID of the user
    recipe_id: int  # ID of the recipe to add to favorites

@app.post("/add_favorite_recipe/")
async def add_favorite_recipe(data: AddFavoriteRequest, db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.user_id == data.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if the recipe is already in the favorites list
    if user.favorite_recipes is None:
        user.favorite_recipes = []

    if data.recipe_id in user.favorite_recipes:
        raise HTTPException(status_code=400, detail="Recipe already in favorites")

    # Add the recipe to the user's favorites
    updated_favorites = user.favorite_recipes + [data.recipe_id]
    user.favorite_recipes = updated_favorites

    # Commit the changes to the database
    db.commit()
    db.refresh(user)

    return {"message": "Recipe added to favorites", "user_id": data.user_id, "favorite_recipes": user.favorite_recipes}

class removeFavoriteRequest(BaseModel):
    user_id: int
    recipe_id: int

@app.post("/remove_favorite_recipe/")
async def remove_favorite_recipe(data: removeFavoriteRequest, db: Session = Depends(get_db)):
    user = db.query(Users).filter(Users.user_id == data.user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if the recipe is not in the favorites list
    if user.favorite_recipes is None or data.recipe_id not in user.favorite_recipes:
        raise HTTPException(status_code=400, detail="Recipe not in favorites")
    
    if data.recipe_id in user.favorite_recipes:
        copy_favorites = []
        copy_favorites = user.favorite_recipes
        copy_favorites.remove(data.recipe_id)
        user.favorite_recipes = copy_favorites

    db.commit()
    db.refresh(user)

    return {"message": "Recipe has been removed from favorites", "user_id": data.user_id, "favorite_recipes": user.favorite_recipes}

@app.post("/fetch_recipe_by_id/")
async def fetch_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe_details = db.query(Recipes).filter(Recipes.recipe_id == recipe_id).first()


    if not recipe_details:
        raise HTTPException(status_code=404, detail="Recipe not in Recipes")
    
    return recipe_details

@app.post("/fetch_recipe_by_name/")
async def fetch_recipe(recipe_name: str, db: Session = Depends(get_db)):
    # Fetch exact match
    recipe_details = db.query(Recipes).filter(Recipes.name == recipe_name).first()

    # If an exact match is found, return it
    if recipe_details:
        return recipe_details

    # If no exact match, fetch all recipes
    all_recipes = db.query(Recipes).all()

    # Filter recipes using fuzzy matching
    filtered_recipes = [
        recipe for recipe in all_recipes
        if fuzz.ratio(recipe.name.lower(), recipe_name.lower()) > 70
    ]

    return filtered_recipes


# SHOPPING LIST QUERIES -------------------------------------------------------------------------------------------------------------------------------------

#Generate Shopping List
@app.post("/shopping_list/")
async def shopping_list(user_id: int, db: Session = Depends(get_db) ):

    #fetch planned meals of the individual user and those that are shared with them
    planned_meals = db.query(PlannedMeals).options(joinedload(PlannedMeals.recipe)).filter(
        or_(
            PlannedMeals.user_id == user_id,
            and_(
                PlannedMeals.is_shared == True,
                user_id == any_(PlannedMeals.shared_with)
            )
        )
    ).all()

    # Collect unique users
    unique_users = {user_id}  # Initialize with the given user_id

    # Create user_matches_by_meal
    user_matches_by_meal = []
    for meal in planned_meals:
        user_list = [meal.user_id] + meal.shared_with
        user_matches_by_meal.append(user_list)
        unique_users.update(user_list)  # Add all users from this meal to unique_users

    # Convert unique_users to a sorted list
    unique_users = sorted(unique_users)

    # Generate all combinations of user IDs
    all_combinations = []
    for r in range(1, len(unique_users) + 1):
        all_combinations.extend(combinations(unique_users, r))

    # Convert tuples to lists
    all_combinations = [list(comb) for comb in all_combinations]

    for i in range(len(all_combinations) -1, -1, -1):
        if len(all_combinations[i]) == 1:
            del all_combinations[i]

    #fetches the planned meal info (meal_id, users oon meal, ingredient names, quantities, units) and scales/converts info
    meal_info = []

    for meal in planned_meals:
        meal_id = meal.meal_id
        users = []
        users.append(meal.user_id)
        users.append(meal.shared_with)
        users = sorted(users)
        #query recipe table (recipes_good for meal info)
        recipe_details = db.query(Recipes).filter(Recipes.recipe_id == meal.recipe_id).first()
        ingredient_names = recipe_details.ingredients
        quantities = recipe_details.ingredient_quantities
        quantities = [num * (meal.n_servings/recipe_details.serving_size) for num in quantities]
        units = recipe_details.ingredient_units
        quantities = convert_list_to_grams(quantities, units)
        indv_meal_info = [meal_id, users, ingredient_names, quantities, units]
        meal_info.append(indv_meal_info)


    #fetches the proper user inventory sets for calculating the shopping list
    inventory_info = []

    #individual pantries info gathering
    for user in unique_users:
        users = []
        users.append(user)
        inv = db.query(Pantry).filter(
            and_(
                Pantry.user_id == user,  # User ID matches the provided user
                not_(
                    or_(
                        *(Pantry.shared_with.contains([u]) for u in unique_users)  # No unique_users IDs in shared_with
                    )
                )
            )
        ).all()
        ingredient_names = [pantry_item.food_name for pantry_item in inv]
        quantities = [pantry_item.quantity for pantry_item in inv]
        units = [pantry_item.unit for pantry_item in inv]
        quantities = convert_list_to_grams(quantities, units)
        pantry_info = [users, ingredient_names, quantities, units]
        inventory_info.append(pantry_info)

    #pantry info gathering of combinations where user_id is in the combo and meal.shared_with contains 
    # the others in the combo but no other unique users (part 2)
    for combo in all_combinations:
        inv = db.query(Pantry).filter(
            and_(
                # Condition 1: Pantry.user_id is equal to one of the user IDs in the combo
                Pantry.user_id.in_(combo),

                # Condition 2: Pantry.shared_with contains the other user IDs in the combo
                Pantry.shared_with.contains([user for user in combo if user != Pantry.user_id]),

                # Condition 3: Pantry.shared_with contains no user_ids in unique_users besides the IDs in the combo
                not_(
                    or_(
                        *(Pantry.shared_with.contains([user]) for user in unique_users if user not in combo)
                    )
                )
            )
        ).all()
        ingredient_names = [pantry_item.food_name for pantry_item in inv]
        quantities = [pantry_item.quantity for pantry_item in inv]
        units = [pantry_item.unit for pantry_item in inv]
        quantities = convert_list_to_grams(quantities, units)
        pantry_info = [combo, ingredient_names, quantities, units]
        inventory_info.append(pantry_info)

    #pantries info gathering of combinations of associated users in meal where they are in the shared_with
    #and the user_id of the item is not aninvolved user in the meal planning(part 3)
    for combo in all_combinations:
        inv = db.query(Pantry).filter(
            and_(
                # Condition 1: Pantry.user_id is not in unique_users
                not_(Pantry.user_id.in_(unique_users)),

                # Condition 2: Pantry.shared_with contains all user IDs in combo
                Pantry.shared_with.contains(combo),

                # Condition 3: Pantry.shared_with must not contain other IDs from unique_users
                not_(
                    or_(
                        *(Pantry.shared_with.contains([user]) for user in unique_users if user not in combo)
                    )
                )
            )
        ).all()
        ingredient_names = [pantry_item.food_name for pantry_item in inv]
        quantities = [pantry_item.quantity for pantry_item in inv]
        units = [pantry_item.unit for pantry_item in inv]
        quantities = convert_list_to_grams(quantities, units)
        pantry_info = [combo, ingredient_names, quantities, units]
        inventory_info.append(pantry_info)
    
    #pantry info gathering where the item is shared with just one unique user from unique_users
    #  and the user_id is not in unique_users
    for user in unique_users:
        inv = db.query(Pantry).filter(
            and_(
                # Condition 1: Pantry.user_id is not equal to any user in unique_users
                not_(Pantry.user_id.in_(unique_users)),

                # Condition 2: The user being checked is the only unique user in Pantry.shared_with
                Pantry.shared_with == [user]
            )
        ).all()
        ingredient_names = [pantry_item.food_name for pantry_item in inv]
        quantities = [pantry_item.quantity for pantry_item in inv]
        units = [pantry_item.unit for pantry_item in inv]
        quantities = convert_list_to_grams(quantities, units)
        pantry_info = [user, ingredient_names, quantities, units]
        inventory_info.append(pantry_info)

        #math calculation of needed ingredients and amounts
        for meal in meal_info:
            for pantry in inventory_info:
                if all(user in meal[2] for user in pantry[0]):
                    for idx_meal, ingredient in enumerate(meal[2]):
                        highest_score = 0
                        best_match_index = None  # To store the index of the best matching item

                        for idx_inv, item in enumerate(pantry[1]):
                            # Calculate the similarity ratio
                            ratio = fuzz.ratio(ingredient.lower(), item.lower())

                            # Update the highest score and best match index if ratio > 70
                            if ratio > 70 and ratio > highest_score and meal[3][idx_inv] > 0 and pantry[1][idx_inv] > 0:
                                highest_score = ratio
                                best_match_index = idx_inv

                        # If a match is found, print or store the result
                        if best_match_index is not None:
                            if meal[3][idx_meal] <= pantry[1][best_match_index]:
                                pantry[1][best_match_index] -= meal[3][idx_meal]
                                meal[3][idx_meal] = 0
                            else:
                                meal[3][idx_meal] -= pantry[1][best_match_index]
                                pantry[1][best_match_index] = 0
    #convert units back
    for meal in meal_info:
        meal[3] = convert_list_from_grams(meal[3], meal[4])

    shopping_list = []

    for meal in meal_info:
        #remove 0 quantities here
        for zero_idx in range(len(meal[3]) - 1, -1, -1):  # Iterate backward
            if meal[3][zero_idx] == 0:
                del meal[2][zero_idx]
                del meal[3][zero_idx]
                del meal[4][zero_idx]
        if len(shopping_list) != 0: #if shoppinglist doesn't have any shopping info yet then add first group
            for idx_match, group in enumerate(shopping_list):
                group_match_index = None
                if sorted(meal[1]) == sorted(group[0]):
                    group_match_index = idx_match
            if group_match_index != None:
                for ingredient_idx, ingredient_name in enumerate(meal[2]):
                    match_found = False
                    for shop_idx, item_name in enumerate(shopping_list[group_match_index][1]):
                        if item_name == ingredient_name:
                            match_found = True
                            shopping_list[group_match_index][2][shop_idx] += meal[3][ingredient_idx]
                    if match_found == False:
                        shopping_list[group_match_index][1].append(ingredient_name)
                        shopping_list[group_match_index][2].append(meal[3][ingredient_idx])
                        shopping_list[group_match_index][3].append(meal[4][ingredient_idx])
            else:
                new_group = []
                new_group.append(meal[1])
                new_group.append(meal[2])
                new_group.append(meal[3])
                new_group.append(meal[4])
                shopping_list.append(new_group)
        else:
            new_group = []
            new_group.append(meal[1])
            new_group.append(meal[2])
            new_group.append(meal[3])
            new_group.append(meal[4])
            shopping_list.append(new_group) #add new group line

    #fix shopping_list format
    for idx in range(len(shopping_list)):
        shopping_list[idx].append(shopping_list[idx][0])
        shopping_list[idx].append(shopping_list[idx][1])
        shopping_list[idx].append(shopping_list[idx][2])
        shopping_list[idx].append(shopping_list[idx][3])
        del shopping_list[idx][0]

    #a matrix of lists - return_matrix [x][3] - matrix dimensions
    #return_matrix [x] - each row is a list of things to shop based on users for shared meal groups
    #return_matrix [x][0] - column 0 is the list of users for that shoppiing list portion (starting user's individual shopping list)
    #return_matrix [x][1] - column 1 is the list of the ingredients to be shopped for that group
    #return_matrix [x][2] - column 2 is the of list of quantities for the ingredients
    #return_matrix [x][3] - column 3 is the list of units for the ingredients
    return shopping_list

class shoppingItem(BaseModel):
    food_name: str
    quantity: float
    unit: str
    user_id: int
    expiration_date: Optional[datetime] = None
    category: Optional[str] = None
   
@app.post("/item_shopped/")
async def item_shopped(data: shoppingItem, db: Session = Depends(get_db)):
    pantry_items = db.query(Pantry).filter(Pantry.user_id == shoppingItem.user_id).all()

    exists = False
    best_match_score = 0
    edit_item= None

    for item in pantry_items:
        fuzz_score = fuzz.ratio(item.food_name.lower(), shoppingItem.food_name.lower())
        if fuzz_score > 70 and fuzz_score > best_match_score:
            best_match_score = fuzz_score
            exists = True
            edit_item = db.query(Pantry).filter(Pantry.pantry_id == item.pantry_id).first()

    if not exists:
        pantry_item = Pantry(
            food_name = shoppingItem.food_name,
            quantity = shoppingItem.quantity,
            unit = shoppingItem.unit,
            user_id = shoppingItem.user_id,
            added_date = datetime.now(),
            expiration_date = shoppingItem.expiration_date if shoppingItem.expiration_date else None,
            category = shoppingItem.category if shoppingItem.category else None,
            comment = None,
            is_shared = False,
            shared_with = [],
            location = None,
            price = None
        )

        db.add(pantry_item)
        db.commit()

        return pantry_item
    else:
        edit_item.quantity = convert_from_grams(convert_to_grams(edit_item.quantity, edit_item.unit) + convert_to_grams(shoppingItem.quantity, shoppingItem.unit), shoppingItem.unit)
        edit_item.unit = shoppingItem.unit
        edit_item.food_name = shoppingItem.food_name
        edit_item.added_date = datetime.now()
        edit_item.expiration_date = shoppingItem.expiration_date if shoppingItem.expiration_date else edit_item.expiration_date
        edit_item.category = shoppingItem.category if shoppingItem.category else edit_item.category

        db.commit()
        db.refresh(edit_item)

        return edit_item



            
