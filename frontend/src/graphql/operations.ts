// Operaciones GraphQL tipadas: `npm run codegen` genera sus tipos en src/gql a partir del
// contrato (docs/contratos/schema.graphql). Cada vista pide SOLO los campos que muestra:
// los fragments describen lo que necesita cada tarjeta (sin over-fetching).
import { graphql } from "../gql";

// --------------------------------------------------------------------------- sesión

export const ME = graphql(`
  query Me {
    me {
      id
      email
      fullName
    }
  }
`);

export const LOGIN = graphql(`
  mutation Login($input: LoginInput!) {
    login(input: $input) {
      user {
        id
        email
        fullName
      }
    }
  }
`);

export const REGISTER = graphql(`
  mutation Register($input: RegisterInput!) {
    register(input: $input) {
      user {
        id
        email
        fullName
      }
    }
  }
`);

export const LOGOUT = graphql(`
  mutation Logout {
    logout
  }
`);

// --------------------------------------------------------------------------- catálogo

export const CATALOG_STATUS = graphql(`
  query CatalogStatus {
    catalogStatus {
      catalog
      totalOffers
      lastSyncAt
    }
  }
`);

export const FLIGHT_CARD = graphql(`
  fragment FlightCard on FlightOffer {
    id
    airline
    operatedBy
    origin
    destination
    departureAt
    arrivalAt
    durationMinutes
    stops
    price
    originalPrice
    originalCurrency
    seatsAvailable
  }
`);

export const HOTEL_CARD = graphql(`
  fragment HotelCard on HotelOffer {
    id
    hotelName
    stars
    categoryName
    zoneName
    roomName
    boardName
    nights
    pricePerNight
    priceTotal
    originalPrice
    originalCurrency
    roomsAvailable
  }
`);

export const CAR_CARD = graphql(`
  fragment CarCard on CarOffer {
    id
    company
    model
    category
    transmission
    seats
    days
    pricePerDay
    priceTotal
    unitsAvailable
  }
`);

// Una sola petición para todo el constructor de paquetes (vuelos + hoteles + autos + sugeridos).
export const SEARCH_OFFERS = graphql(`
  query SearchOffers(
    $flights: FlightSearchInput!
    $hotels: HotelSearchInput!
    $cars: CarSearchInput!
    $packages: PackageSearchInput!
  ) {
    flights: searchFlights(input: $flights) {
      ...FlightCard
    }
    hotels: searchHotels(input: $hotels) {
      ...HotelCard
    }
    cars: searchCars(input: $cars) {
      ...CarCard
    }
    packages: searchPackages(input: $packages) {
      flight {
        ...FlightCard
      }
      hotel {
        ...HotelCard
      }
      car {
        ...CarCard
      }
      estimatedPrice {
        subtotal
        taxes
        total
      }
    }
  }
`);

// --------------------------------------------------------------------------- órdenes y SAGA

export const BOOK_PACKAGE = graphql(`
  mutation BookPackage($input: BookPackageInput!) {
    bookPackage(input: $input) {
      order {
        id
        status
      }
    }
  }
`);

export const ORDER_DETAIL = graphql(`
  query OrderDetail($id: ID!) {
    order(id: $id) {
      id
      status
      passengers
      rooms
      subtotal
      taxes
      totalAmount
      currency
      createdAt
      flight {
        ...FlightCard
      }
      hotel {
        ...HotelCard
      }
      car {
        ...CarCard
      }
      payment {
        status
        amount
        providerRef
      }
      invoice {
        number
        total
        issuedAt
      }
      saga {
        id
        status
        currentStep
        failureReason
        simulatedFailureAt
        steps {
          step
          action
          status
          attempt
          errorCode
          errorMessage
          startedAt
          finishedAt
        }
      }
    }
  }
`);

export const MY_ORDERS = graphql(`
  query MyOrders {
    myOrders(limit: 20) {
      id
      status
      totalAmount
      currency
      passengers
      createdAt
      saga {
        status
        simulatedFailureAt
      }
    }
  }
`);
