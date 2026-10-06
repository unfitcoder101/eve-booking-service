SIGNUP = {"email": "x@example.com", "password": "Password123", "full_name": "X"}
                    
                            
def test_signup_and_login(client):
    r = client.post("/auth/signup", json=SIGNUP)
    assert r.status_code == 201
    assert "password" not in r.json()                         
    r = client.post("/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]})                       
    assert r.status_code == 200                        
    assert r.json()["access_token"]                         


def test_duplicate_email_rejected(client):
    assert client.post("/auth/signup", json=SIGNUP).status_code == 201                    
    assert client.post("/auth/signup", json=SIGNUP).status_code == 409                                


def test_short_password_rejected(client):                   
    r = client.post("/auth/signup", json={**SIGNUP, "password": "short"})                             
    assert r.status_code == 422                                 


def test_wrong_password_rejected(client, user):                           
    r = client.post("/auth/login", json={"email": "a@example.com", "password": "WrongPass123"})                   
    assert r.status_code == 401                   


def test_protected_route_needs_token(client):                     
    assert client.get("/auth/me").status_code in (401, 403)                           
