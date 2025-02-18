from flask import Flask, request, jsonify, session
from flask_bcrypt import Bcrypt
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from flask_cors import CORS
import os
from dotenv import load_dotenv
import google.generativeai as genai
import base64
from io import BytesIO
from PIL import Image


app = Flask(__name__)
load_dotenv()

app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")


mongo = PyMongo(app)
bcrypt = Bcrypt(app)
CORS(app)

# Collection
donors = mongo.db.donors
organizations = mongo.db.organizations
donors_collection =mongo.db.donors_collection
donations_collection = mongo.db["donations"]
oraganisation_collection = mongo.db["oraganisation_collection"]
accepted_requests_collection = mongo.db["accepted_requests"]  # New collection
declined_requests_collection = mongo.db["declined_requests"] 

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    user_type = data.get("user_type")

    if not ( email and password):
        return jsonify({"error": "All fields are required"}), 400
    


    if user_type != "donor":
        existing_user = organizations.find_one({"email": email})
        if existing_user:
            return jsonify({"error": "Email already exists"}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        organizations_id = organizations.insert_one({ "email": email, "password": hashed_password,"Details" : "No"}).inserted_id

        return jsonify({"message": "Registration successful", "organizations_id": str(organizations_id)}), 201




    if user_type == "donor":
        existing_user = donors.find_one({"email": email})
        if existing_user:
            return jsonify({"error": "Email already exists"}), 400

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        donor_id = donors.insert_one({ "email": email, "password": hashed_password,"Details" : "No"}).inserted_id

        return jsonify({"message": "Registration successful", "donor_id": str(donor_id)}), 201




@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    user_type = data.get("user_type")



    if user_type == "donor":
        donor = donors.find_one({"email": email})
        if not donor or not bcrypt.check_password_hash(donor["password"], password):
            return jsonify({"error": "Invalid email or password"}), 401

        session["donor_id"] = str(donor["_id"])

        if donor["Details"] == "Yes":
            return jsonify({"message": "Login successful", "donor_id": session["donor_id"], "Details": "Yes"}), 200
        return jsonify({"message": "Login successful", "donor_id": session["donor_id"],"Details": "No"}), 200
    

    if user_type != "donor":
        organization = organizations.find_one({"email": email})
        if not organization or not bcrypt.check_password_hash(organization["password"], password):
            return jsonify({"error": "Invalid email or password"}), 401
        

        session["organizations_id"] = str(organization["_id"])
        if organization["Details"] == "Yes":
            return jsonify({"message": "Login successful", "organizations_id": session["organizations_id"], "Details": "Yes"}), 200
        return jsonify({"message": "Login successful", "organizations_id": session["organizations_id"],"Details": "No"}), 200




@app.route("/logout", methods=["POST"])
def logout():
    session.pop("donor_id", None)
    return jsonify({"message": "Logged out successfully"}), 200





@app.route("/donor", methods=["POST"])
def get_donor():
  
  try:
    data = request.json
    full_name = data.get("full_name")
    email = data.get("email")
    phone_number = data.get("phone_number")
    address = data.get("address")
    donation_preferences = data.get("donation_preferences")
    donor_id = data.get("donor_id")

   


    required_fields = ["full_name", "phone_number", "address", "donation_preferences"]
    for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({"error": f"Missing field: {field}"}), 400
                

    existing_donor = donors_collection.find_one({"donor_id": data["donor_id"]})
    if existing_donor:
        return jsonify({"error": "Donor profile already exists"}), 400

    donors_id = donors_collection.insert_one({
                "full_name": data["full_name"],
                "phone_number": data["phone_number"],
                "address": data["address"],
                "donation_preferences": data["donation_preferences"],
                "donor_id": data["donor_id"] 
            }).inserted_id
    
    donor_i=donors.update_one({"_id": ObjectId(donor_id)}, {"$set": {"Details": "Yes"}})

    return jsonify({"message": "Profile created successfully!", "donor_id": str(donor_id)}), 201

  except Exception as e:
    return jsonify({"error": str(e)}), 500


    


@app.route('/donordetails', methods=['GET'])
def get_donor_details():
    try:
        data = request.args.get("donor_id")
        donor = donors_collection.find_one({"donor_id": data})  

        if not donor:
            return jsonify({"error": "Donor not found"}), 404

        donor_data = {
            "full_name": donor["full_name"],
            "totalDonations": donor["total_donations"] if "total_donations" in donor else 0,
            "itemsDonated": donor["items_donated"] if "items_donated" in donor else 0,
            "lastDonation": donor["last_donation"] if "last_donation" in donor else None,
            "impactScore": donor["impact_score"] if "impact_score" in donor else 0,
            "recentDonations": donor["recent_donations"] if "recent_donations" in donor else [],
            "address":donor["address"]
        }

        return jsonify(donor_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/donorInfo', methods=['GET'])
def get_donor_info():
    try:
       
        donor_ids = request.args.get("donor_ids")
        if not donor_ids:
            return jsonify({"error": "No donor_ids provided"}), 400

      
        donor_id_list = donor_ids.split(',')

     
        donors = donors_collection.find({"donor_id": {"$in": donor_id_list}})

       
        donor_data_list = []
        for donor in donors:
            donor_data = {
                "donor_id": donor["donor_id"],
                "full_name": donor["full_name"],
                
                "address": donor.get("address", "Address not available")
            }
            donor_data_list.append(donor_data)

        # If no donors are found, return a 404 error
        if not donor_data_list:
            return jsonify({"error": "No donors found"}), 404

        return jsonify(donor_data_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

import uuid

@app.route('/imageupload', methods=['POST'])
def image_upload():
    try:
        data = request.json
        image_data = data.get("image")  # Base64 encoded image

        if not image_data:
            return jsonify({"error": "No image data provided"}), 400

        # Decode the base64 image
        image_data = image_data.split(",")[1]
        image = Image.open(BytesIO(base64.b64decode(image_data)))

        # Save the image to a unique file path
        image_filename = f"image_{uuid.uuid4()}.png"
        image.save(image_filename)

       
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(model_name="models/gemini-2.0-flash")
        prompt = "Be prefessional and stop telling here's your image description etc.Analyze the image and describe what is shown in simple terms, including the number of items present. If the item appears to be in bad condition (e.g., damaged, worn out, or broken), clearly state that the item is in bad condition."
        response = model.generate_content([image_data, prompt], request_options={"timeout": 600})

        
        os.remove(image_filename)

        return jsonify({"message": "Image uploaded successfully!", "description": response.text}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500



       
@app.route('/donations', methods=['POST'])
def donations():
    try:
        data = request.json
        donor_id = data.get("donor_id")
        condition = data.get("condition")
        number_items = data.get("numberOfItems")
        donation_date = data.get("donation_date")
        additional_notes = data.get("Additional_Notes")
        image = data.get("image")
        response = data.get("apiResponse")
        itemname = data.get("itemname")

        print(data)

        # Validate required fields
        if not (donor_id and condition and donation_date):
            return jsonify({"error": "All fields are required"}), 400

        # Check if donor exists
        existing_donor = donors_collection.find_one({"donor_id": donor_id})
        if not existing_donor:
            return jsonify({"error": "Donor not found"}), 404

        # Update donor's donation details
        total_donations = existing_donor.get("total_donations", 0)
        items_donated = existing_donor.get("items_donated", 0)
        recent_donations = existing_donor.get("recent_donations", [])

        total_donations += 1
        items_donated += number_items if number_items else 0

        # Update donor record
        donors_collection.update_one(
            {"donor_id": donor_id},
            {
                "$set": {
                    "total_donations": total_donations,
                    "items_donated": items_donated,
                    "last_donation": donation_date,
                    "recent_donations": recent_donations

                }
            }
        )

        # Insert donation record
        donation_record = {
            "donor_id": donor_id,
            "condition": condition,
            "number_items": number_items,
            "donation_date": donation_date,
            "additional_notes": additional_notes,
            "image": image,
            "response": response,
            "itemname": itemname
            
        }
        donation_id = donations_collection.insert_one(donation_record).inserted_id

        return jsonify({"message": "Donation recorded successfully!", "donation_id": str(donation_id)}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

   





@app.route('/oraganisationDetails', methods=['POST'])
def organisationDetails():
    try:
        data = request.json
        organisation_name = data.get("organizationName")
        registrationNumber = data.get("registrationNumber")
       
        address = data.get("address")
        organizations_id = data.get("organizations_id")
        headName = data.get("headName")
       
        

        org_i=organizations.update_one({"_id": ObjectId(organizations_id)}, {"$set": {"Details": "Yes"}})
        print(org_i)
        

       
        
        org_id=oraganisation_collection.insert_one({
            "organisation_name": organisation_name,
            "registrationNumber": registrationNumber,
            "address": address,
           
            "organizations_id": organizations_id,
            "headName": headName
        }).inserted_id
        return jsonify({"message": "Details added successfully!", "org_id": str(org_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
       
       
@app.route('/organisationdetails', methods=['GET'])
def organisationdetials():
    try:
        data = request.args.get("organizations_id")
        organisation = oraganisation_collection.find_one({"organizations_id": data})  

        if not organisation:
            return jsonify({"error": "Organisation not found"}), 404

        organisation_data = {
            "organisation_name": organisation["organisation_name"],
            
            "Total_Pickups": organisation["Total_Pickups"] if "Total_Pickups" in organisation else 0,
           
            "Pending_Pickups": organisation["Pending Pickups"] if "Pending Pickups" in organisation else 0,
            "Completed_Today": organisation["Completed Today"] if "Completed Today" in organisation else 0,
        }

        return jsonify(organisation_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    





@app.route('/organisationPickup', methods=['GET'])
def organisationPickup():
    try:
        organisation_id = request.args.get("organizations_id")
        organisationdaonation = donations_collection.find({})
        donations_list = []
        for donation in organisationdaonation:
            donations_list.append({
                "donor_id": donation["donor_id"],
                "condition": donation["condition"],
                "number_items": donation["number_items"],
                "donation_date": donation["donation_date"],
                "additional_notes": donation["additional_notes"],
                "image": donation["image"],
                # "response": donation["response"],
                "itemname": donation["itemname"]
            })

      
        pending_pickups = len(donations_list)
        org_e=oraganisation_collection.update_one({"_id": ObjectId(organisation_id)}, {"$set": {"Pending Pickups": pending_pickups}})
        return jsonify(donations_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    



@app.route('/acceptRequest', methods=['POST'])
def accept_request():
    try:
        data = request.json
        donor_id = data.get("donor_id")
        organisation_id = data.get("organisation_id")

        if not (donor_id and organisation_id):
            return jsonify({"error": "Donor ID and Organisation ID are required"}), 400

        # Find the request in the donations collection
        request_to_accept = donations_collection.find_one({"donor_id": donor_id})
        if not request_to_accept:
            return jsonify({"error": "Request not found"}), 404
        

        #when the request is accepyted update total pickup Pending Pickups Completed Today etx
        existing_organisation = oraganisation_collection.find_one({"organizations_id": organisation_id})
        if not existing_organisation:
            return jsonify({"error": "Organisation not found"}), 404
        
        Total_Pickups = existing_organisation.get("Total_Pickups", 0) + 1
        org_e = oraganisation_collection.update_one({"_id": ObjectId(organisation_id)}, {"$set": {"Total_Pickups": Total_Pickups}}) 
       



        # Move the request to the accepted_requests collection
        accepted_request = {
            "donor_id": request_to_accept["donor_id"],
            "condition": request_to_accept["condition"],
            "number_items": request_to_accept["number_items"],
            "donation_date": request_to_accept["donation_date"],
            "additional_notes": request_to_accept["additional_notes"],
            "image": request_to_accept["image"],
            "itemname": request_to_accept["itemname"],
            "organisation_id": organisation_id,
            "status": "accepted"
        }
        accepted_requests_collection.insert_one(accepted_request)

        # Remove the request from the donations collection
        donations_collection.delete_one({"donor_id": donor_id})

        return jsonify({"message": "Request accepted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# New endpoint to decline a pickup request
@app.route('/declineRequest', methods=['POST'])
def decline_request():
    try:
        data = request.json
        donor_id = data.get("donor_id")
        organisation_id = data.get("organisation_id")

        if not (donor_id and organisation_id):
            return jsonify({"error": "Donor ID and Organisation ID are required"}), 400

        # Find the request in the donations collection
        request_to_decline = donations_collection.find_one({"donor_id": donor_id})
        if not request_to_decline:
            return jsonify({"error": "Request not found"}), 404

        # Move the request to the declined_requests collection
        declined_request = {
            "donor_id": request_to_decline["donor_id"],
            "condition": request_to_decline["condition"],
            "number_items": request_to_decline["number_items"],
            "donation_date": request_to_decline["donation_date"],
            "additional_notes": request_to_decline["additional_notes"],
            "image": request_to_decline["image"],
            "itemname": request_to_decline["itemname"],
            "organisation_id": organisation_id,
            "status": "declined"
        }
        declined_requests_collection.insert_one(declined_request)

        # Remove the request from the donations collection
        donations_collection.delete_one({"donor_id": donor_id})

        return jsonify({"message": "Request declined successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/req_accept', methods=['GET'])
def get_accepted_requests():
    try:
        # Fetch all accepted requests
        accepted_requests = accepted_requests_collection.find({})
        accepted_requests_list = []
        for request in accepted_requests:
            accepted_requests_list.append({
                "donor_id": request["donor_id"],
                "condition": request["condition"],
                "number_items": request["number_items"],
                "donation_date": request["donation_date"],
                "additional_notes": request["additional_notes"],
                "image": request["image"],
                "itemname": request["itemname"],
                "organisation_id": request["organisation_id"],
                "status": request["status"]
            })

        return jsonify(accepted_requests_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/req_decline', methods=['GET'])
def get_declined_requests():
    try:
        # Fetch all declined requests
        declined_requests = declined_requests_collection.find({})
        declined_requests_list = []
        for request in declined_requests:
            declined_requests_list.append({
                "donor_id": request["donor_id"],
                "condition": request["condition"],
                "number_items": request["number_items"],
                "donation_date": request["donation_date"],
                "additional_notes": request["additional_notes"],
                "image": request["image"],
                "itemname": request["itemname"],
                "organisation_id": request["organisation_id"],
                "status": request["status"]
            })

        return jsonify(declined_requests_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 8000))
        print(f"Starting app on port {port}...")  # Debugging
        app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as e:
        print(f"Failed to start app: {e}")  # Debugging