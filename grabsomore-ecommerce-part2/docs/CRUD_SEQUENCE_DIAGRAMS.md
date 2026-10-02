# Task 1 — Store, product and review CRUD sequence diagrams

These sequence diagrams describe the implemented Part 2 routes. GitHub renders the Mermaid blocks directly; open this file on GitHub to see the diagrams. The three diagrams together cover all **12 CRUD use cases**. Each operation is a separate request, not a requirement to create, edit and delete a resource in one visit.

| Resource | Create | Read | Update | Delete |
| --- | --- | --- | --- | --- |
| Store | Vendor: `POST /ecommerce/api/stores/` | Buyer/vendor: `GET /ecommerce/api/stores/` or `<id>/` | Owning vendor: `PUT/PATCH /ecommerce/api/stores/<id>/` | Owning vendor: `DELETE /ecommerce/api/stores/<id>/` |
| Product | Vendor: `POST /ecommerce/api/products/` | Buyer/vendor: `GET /ecommerce/api/products/` or `<id>/` | Owning vendor: `PUT/PATCH /ecommerce/api/products/<id>/` | Owning vendor: `DELETE /ecommerce/api/products/<id>/` |
| Review | Buyer: `POST /ecommerce/products/<id>/review/` | Buyer/vendor: `GET /ecommerce/api/reviews/` | Owning buyer: `POST /ecommerce/products/<id>/review/` | Owning buyer: `POST /ecommerce/reviews/<id>/delete/` |

HTML store/product forms provide equivalent owner-restricted management. Review API endpoints remain read-only; review writes use the authenticated buyer's HTML form. Session-authenticated changes require CSRF tokens. An API access failure returns 401/403; invalid input returns 400. HTML requests redirect anonymous users to login. Ownership-scoped HTML lookups return 404 for another account's resource.

## Resource and endpoint design

The API uses JSON. Store objects expose an ID, name, description and vendor username. Product objects expose their store ID, name, description, decimal price as a string, and stock. Review objects expose the product ID, reviewer username, rating, text, timestamp and a computed verification boolean. Private account fields are excluded. Collection URLs use plural resource names; nested URLs scope stores by vendor and products/reviews by their parent resource. HTML forms handle buyer review writes, while the review API satisfies the brief's retrieval requirement.

## 1. Store CRUD

```mermaid
sequenceDiagram
    actor User as Buyer or vendor
    participant UI as Browser / API client
    participant Auth as Django / DRF authentication
    participant API as Store API
    participant DB as Database

    User->>UI: Open Web API → Store API
    UI->>Auth: Authenticated request (session or Basic)
    Auth->>API: Identity + role (CSRF checked for session writes)
    alt Anonymous or no buyer/vendor role
        API-->>UI: Reject access (401/403)
    else Permitted catalogue role
        opt CREATE — vendor only
            UI->>API: POST /api/stores/ (name, description)
            API->>API: Require Vendors role, validate name
            API->>DB: INSERT Store(owner = request.user)
            DB-->>API: Store ID
            API-->>UI: 201 Created (owner cannot be supplied)
        end
        opt READ — buyer or vendor
            UI->>API: GET /api/stores/ or /api/stores/id/
            API->>DB: SELECT stores with owner
            DB-->>API: Store records (or none)
            API-->>UI: 200 JSON (404 for unknown detail)
        end
        opt UPDATE — owning vendor only
            UI->>API: PUT/PATCH /api/stores/id/
            API->>DB: SELECT store
            API->>API: Require vendor role and owner == request.user
            alt Wrong owner or buyer
                API-->>UI: 403, no change
            else Owner with valid data
                API->>DB: UPDATE name/description, keep owner
                API-->>UI: 200 updated store
            end
        end
        opt DELETE — owning vendor only
            UI->>API: DELETE /api/stores/id/
            API->>DB: SELECT store
            API->>API: Require vendor role and ownership
            API->>DB: DELETE store, products and their reviews
            Note over DB: Invoice line snapshots survive, product references become NULL
            API-->>UI: 204 No Content (403 for wrong owner)
        end
    end
```

## 2. Product CRUD

```mermaid
sequenceDiagram
    actor Vendor
    actor Reader as Buyer or vendor
    participant API as Authenticated Product API
    participant Form as Serializer / permission checks
    participant DB as Database

    opt CREATE
        Vendor->>API: POST /api/products/ (store, name, price, stock)
        API->>Form: Check vendor role, fields and selected store owner
        alt Store belongs to another vendor or input invalid
            Form-->>API: Validation error
            API-->>Vendor: 400, no product created
        else Valid owned store
            Form->>DB: INSERT product linked to store
            DB-->>API: Product ID
            API-->>Vendor: 201 Created
        end
    end
    opt READ
        Reader->>API: GET /api/products/ or /api/products/id/
        API->>Form: Require buyer or vendor role
        API->>DB: SELECT product(s) and store
        DB-->>API: Records
        API-->>Reader: 200 JSON (404 for unknown ID)
        Reader->>API: GET /api/stores/id/products/
        API->>DB: SELECT products WHERE store_id = selected store
        API-->>Reader: 200 JSON scoped to that store
    end
    opt UPDATE
        Vendor->>API: PUT/PATCH /api/products/id/
        API->>DB: SELECT product and current store
        API->>Form: Require current store owner, validate data
        Note over Form: Any replacement store must also belong to this vendor
        alt Unauthorized or invalid
            API-->>Vendor: 403 ownership / 400 validation
        else Valid owner request
            Form->>DB: UPDATE product
            API-->>Vendor: 200 updated product
        end
    end
    opt DELETE
        Vendor->>API: DELETE /api/products/id/
        API->>DB: SELECT product and owner
        API->>Form: Require owning vendor
        alt Wrong owner
            API-->>Vendor: 403, no change
        else Owner
            API->>DB: DELETE product and associated reviews
            Note over DB: Purchased invoice names/prices/quantities remain saved
            API-->>Vendor: 204 No Content
        end
    end
```

## 3. Review CRUD and purchase verification

```mermaid
sequenceDiagram
    actor Buyer
    actor Vendor
    participant UI as Product page / My Reviews
    participant View as Authenticated view / API
    participant DB as Database

    opt CREATE
        Buyer->>UI: Choose Write or edit my review
        UI->>View: GET /products/product_id/review/
        View->>View: Require Buyers role
        View->>DB: Find product and this buyer's existing review
        View-->>UI: Empty form when no review exists
        Buyer->>View: POST rating (1–5), comment, CSRF token
        View->>View: Validate rating and comment, ignore identity/verified fields
        View->>DB: INSERT review with request.user + product
        View-->>Buyer: 302 to product details
    end
    opt READ
        Buyer->>View: GET product details or /api/products/product_id/reviews/
        View->>DB: SELECT reviews and matching invoice items
        Note over View,DB: Verified only if invoice buyer and product both match
        View-->>Buyer: Reviews with verified/unverified status
        Vendor->>UI: Open My Reviews from menu
        UI->>View: GET /my/reviews/?q=...&store=...
        View->>DB: SELECT reviews WHERE product.store.owner = vendor
        View-->>UI: Filtered, paginated reviews across own stores
    end
    opt UPDATE
        Buyer->>View: POST /products/product_id/review/ with new content
        View->>View: Require buyer role and valid form
        View->>DB: UPDATE review WHERE buyer = request.user AND product matches
        Note over View: Cannot edit another buyer's review or set verification
        View-->>Buyer: 302 to updated product details
    end
    opt DELETE
        Buyer->>UI: Choose Delete my review
        UI->>View: POST /reviews/review_id/delete/ with CSRF token
        View->>DB: Find review WHERE buyer = request.user
        alt Not owned / buyer role missing
            View-->>Buyer: 404 / 403, no change
        else Owned review
            View->>DB: DELETE review
            View-->>Buyer: 302 to product details
        end
    end
```

All paths above have the `/ecommerce/` prefix (omitted in some arrows for readability). An unverified review is allowed: purchasing is required for the verified label, not for writing feedback. A later successful checkout changes the displayed status automatically.
