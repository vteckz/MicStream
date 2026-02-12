cmake_minimum_required(VERSION 3.14)
project(btservice_only CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS_INIT} -Wall -fPIC")
set(CMAKE_CXX_FLAGS_RELEASE "-g -O3")
set(CMAKE_AUTOMOC ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "/home/pi/aasdk/cmake_modules/")

# Find packages
set(Boost_USE_STATIC_LIBS OFF)
set(Boost_USE_MULTITHREADED ON)
add_definitions(-DBOOST_ALL_DYN_LINK -DNDEBUG -DRASPBERRYPI3)

find_package(Boost REQUIRED COMPONENTS system log_setup log)
find_package(Qt5 COMPONENTS Bluetooth Network MultimediaWidgets REQUIRED)
find_package(Protobuf REQUIRED)

# aap_protobuf - use installed version
find_path(AAP_PROTOBUF_INCLUDE_DIR aap_protobuf PATHS /home/pi/aasdk/build/protobuf /usr/local/include)
find_library(AAP_PROTOBUF_LIB aap_protobuf PATHS /home/pi/aasdk/build/lib /usr/local/lib)

# aasdk - use installed version  
find_path(AASDK_INCLUDE_DIR aasdk PATHS /usr/local/include)
find_library(AASDK_LIB aasdk PATHS /usr/local/lib /home/pi/aasdk/build/lib)

set(sources_directory ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(include_directory ${CMAKE_CURRENT_SOURCE_DIR}/include)

# btservice sources
file(GLOB btservice_src
    ${sources_directory}/btservice/*.cpp
    ${sources_directory}/autoapp/Configuration/Configuration.cpp
)

add_executable(btservice ${btservice_src})

target_include_directories(btservice PUBLIC
    ${include_directory}
    ${Boost_INCLUDE_DIRS}
    ${Qt5Bluetooth_INCLUDE_DIRS}
    ${Qt5Network_INCLUDE_DIRS}
    ${Qt5MultimediaWidgets_INCLUDE_DIRS}
    ${PROTOBUF_INCLUDE_DIRS}
    ${AAP_PROTOBUF_INCLUDE_DIR}
    ${AASDK_INCLUDE_DIR}
    /home/pi/aasdk/build/protobuf
)

target_link_libraries(btservice PUBLIC
    ${Boost_LIBRARIES}
    Qt5::Bluetooth
    Qt5::Network
    Qt5::MultimediaWidgets
    ${PROTOBUF_LIBRARIES}
    ${AAP_PROTOBUF_LIB}
    ${AASDK_LIB}
)

install(TARGETS btservice RUNTIME DESTINATION bin)
